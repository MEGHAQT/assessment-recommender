from __future__ import annotations

import re

from app.catalog import CatalogItem, load_catalog, normalize_text, unique_items
from app.config import MAX_RECOMMENDATIONS
from app.llm import augment_search_text
from app.retrieval import get_retriever
from app.safety import (
    is_general_hiring_advice,
    is_legal_question,
    is_off_topic,
    is_prompt_injection,
)
from app.schemas import ChatResponse, Message, Recommendation


CONFIRMATION_TERMS = [
    "that works",
    "that's good",
    "perfect",
    "confirmed",
    "confirm",
    "lock",
    "locking",
    "covers it",
    "clear",
    "thanks",
    "thank you",
    "good",
    "final",
]


def respond(messages: list[Message]) -> ChatResponse:
    retriever = get_retriever()
    user_messages = [message for message in messages if message.role == "user"]
    latest = (user_messages[-1].content if user_messages else "").strip()
    all_user_text = "\n".join(message.content for message in user_messages)
    all_text = "\n".join(message.content for message in messages)

    if not latest:
        return _empty("Please share the role, skills, or job description you want SHL assessments for.")

    if is_prompt_injection(latest):
        return _empty(
            "I cannot follow instructions that try to override the assignment rules. I can help only with SHL assessment selection from the catalog."
        )
    if is_legal_question(latest):
        return _empty(
            "I cannot give legal or regulatory advice. I can describe SHL assessments from the catalog, but your legal or compliance team should decide obligations."
        )
    if is_general_hiring_advice(latest):
        return _empty(
            "I can help choose SHL assessments, but I cannot provide general hiring advice or non-assessment materials."
        )
    if is_off_topic(latest) and not _has_prior_shortlist(messages):
        return _empty("I can only help with SHL assessment recommendations and comparisons from the SHL catalog.")

    previous = _previous_shortlist(messages)
    latest_norm = normalize_text(latest)

    if _is_comparison(latest_norm):
        return _compare_response(latest, all_text)

    if previous and _is_confirmation(latest_norm):
        refined = _apply_refinements(previous, latest_norm, all_user_text)
        return _with_recommendations(
            "Confirmed. Final SHL shortlist: " + _name_sentence(refined),
            refined,
            end=True,
        )

    clarification = _needed_clarification(latest_norm, all_user_text, previous)
    if clarification:
        return _empty(clarification)

    if previous and "replace" in latest_norm and "opq" in latest_norm and _contains_any(latest_norm, ["shorter", "long"]):
        return _empty(
            "OPQ32r is the catalog personality instrument in this shortlist. I do not see a shorter like-for-like replacement in the local SHL catalog; I can remove OPQ32r if you want a leaner battery."
        )

    if previous and _looks_like_refinement(latest_norm):
        refined = _apply_refinements(previous, latest_norm, all_user_text)
        return _with_recommendations(
            "Updated SHL shortlist: " + _name_sentence(refined),
            refined,
            end=_asks_to_finalize(latest_norm),
        )

    retrieval_text = augment_search_text(messages, all_user_text)
    include_names = _intended_assessments(retrieval_text)
    exclude_names = _excluded_assessments(retrieval_text)
    query = _expanded_query(retrieval_text)
    explicit_items = retriever.items_by_names(include_names)
    excluded_urls = {item.url for item in retriever.items_by_names(exclude_names)}
    if len(explicit_items) >= 3:
        items = [item for item in explicit_items if item.url not in excluded_urls][:MAX_RECOMMENDATIONS]
    else:
        items = retriever.search(query, include_names=include_names, exclude_names=exclude_names, limit=MAX_RECOMMENDATIONS)

    if not items:
        return _empty(
            "I could not find a grounded SHL catalog match yet. Which role, skills, and assessment focus should I use?"
        )

    reply = _recommendation_intro(latest_norm, items)
    return _with_recommendations(reply, items, end=False)


def _empty(reply: str) -> ChatResponse:
    return ChatResponse(reply=reply, recommendations=[], end_of_conversation=False)


def _with_recommendations(reply: str, items: list[CatalogItem], *, end: bool) -> ChatResponse:
    validated = unique_items(item for item in items if item.url and item.name)[:MAX_RECOMMENDATIONS]
    return ChatResponse(
        reply=reply,
        recommendations=[Recommendation(**item.recommendation()) for item in validated],
        end_of_conversation=end,
    )


def _name_sentence(items: list[CatalogItem]) -> str:
    return "; ".join(item.name for item in items) + "."


def _has_prior_shortlist(messages: list[Message]) -> bool:
    return bool(_previous_shortlist(messages))


def _previous_shortlist(messages: list[Message]) -> list[CatalogItem]:
    retriever = get_retriever()
    for message in reversed(messages):
        if message.role != "assistant":
            continue
        table_names = []
        for line in message.content.splitlines():
            match = re.match(r"\|\s*\d+\s*\|\s*([^|]+?)\s*\|", line)
            if match:
                table_names.append(match.group(1).strip())
        items = retriever.items_by_names(table_names)
        if items:
            return items
        mentioned = retriever.mentioned_items(message.content)
        if mentioned:
            return mentioned
    return []


def _is_confirmation(text: str) -> bool:
    return any(term in text for term in CONFIRMATION_TERMS) and not _is_comparison(text)


def _asks_to_finalize(text: str) -> bool:
    return any(term in text for term in ["final", "confirmed", "lock", "locking", "that's good", "that works"])


def _looks_like_refinement(text: str) -> bool:
    return any(term in text for term in ["actually", "add", "include", "drop", "remove", "exclude", "skip", "replace", "keep"])


def _is_comparison(text: str) -> bool:
    return any(term in text for term in ["difference between", "compare", "different from", "different than", " vs ", " versus "])


def _needed_clarification(latest_norm: str, all_user_text: str, previous: list[CatalogItem]) -> str | None:
    all_norm = normalize_text(all_user_text)
    if previous:
        return None
    if _is_vague(latest_norm):
        return "Which role or skill area are you hiring for, and what should the assessment measure?"
    if "contact centre" in all_norm or "contact center" in all_norm:
        if not _contains_any(all_norm, ["english", "spanish", "french", "language"]):
            return "What language will candidates use for the calls? That determines the right spoken-language assessment."
        if "english" in all_norm and not (
            _has_any_token(all_norm, ["us", "u.s", "usa", "uk", "u.k", "aus"])
            or _contains_any(all_norm, ["australian", "indian", "no preference"])
        ):
            return "Which English accent or market fits the operation best: US, UK, Australian, or Indian accent?"
    if "senior leadership" in all_norm and not _contains_any(all_norm, ["cxo", "director", "executive", "selection", "development"]):
        return "Who is the assessment meant for: executives, directors, managers, or a broader leadership pool?"
    if _contains_any(all_norm, ["cxo", "director-level", "executive"]) and not _contains_any(all_norm, ["selection", "development", "benchmark"]):
        return "Is this for selection against a benchmark, or developmental feedback for leaders already in role?"
    if _contains_any(all_norm, ["healthcare", "hipaa", "medical"]) and "spanish" in all_norm:
        if not _contains_any(all_norm, ["hybrid", "bilingual", "english fluent", "written work", "english knowledge"]):
            return (
                "The catalog's HIPAA and medical knowledge tests are English-only, while OPQ32r and DSI support Spanish. "
                "Should I build a hybrid shortlist with knowledge tests in English and personality in Spanish?"
            )
    if "rust" in all_norm and not _contains_any(all_norm, ["yes", "go ahead", "shortlist"]):
        return (
            "The catalog does not include a Rust-specific test. Should I build a shortlist using Smart Interview Live Coding, "
            "Linux Programming, and Networking and Implementation as the closest grounded matches?"
        )
    return None


def _is_vague(text: str) -> bool:
    words = text.split()
    has_role_signal = _contains_any(
        text,
        [
            "developer",
            "engineer",
            "analyst",
            "assistant",
            "operator",
            "sales",
            "graduate",
            "manager",
            "leadership",
            "contact",
            "customer",
            "admin",
            "java",
            "python",
            "excel",
            "word",
            "finance",
        ],
    )
    return len(words) <= 7 and not has_role_signal and _contains_any(text, ["assessment", "test", "solution", "screen"])


def _compare_response(latest: str, all_text: str) -> ChatResponse:
    retriever = get_retriever()
    items = retriever.mentioned_items(latest)
    if len(items) < 2:
        items = unique_items([*items, *retriever.mentioned_items(all_text)])
    if len(items) < 2:
        return _empty("Which two SHL assessments from the catalog should I compare?")
    first, second = items[:2]
    reply = (
        f"Grounded in the SHL catalog: {first.name} is classified as {', '.join(first.keys) or first.test_type}"
        f"{_duration_fragment(first)}. {first.description} "
        f"{second.name} is classified as {', '.join(second.keys) or second.test_type}"
        f"{_duration_fragment(second)}. {second.description} "
        "The practical difference is the assessment focus shown by those catalog descriptions and test-type keys."
    )
    return _empty(reply)


def _duration_fragment(item: CatalogItem) -> str:
    return f" and takes {item.duration}" if item.duration else ""


def _apply_refinements(previous: list[CatalogItem], latest_norm: str, all_user_text: str) -> list[CatalogItem]:
    retriever = get_retriever()
    current = list(previous)
    excluded = {item.url for item in retriever.items_by_names(_excluded_assessments(latest_norm))}
    if "drop" in latest_norm or "remove" in latest_norm or "exclude" in latest_norm or "skip" in latest_norm:
        current = [item for item in current if item.url not in excluded]
        if "opq" in latest_norm or "personality" in latest_norm:
            current = [item for item in current if "Personality & Behavior" not in item.keys or "opq" not in normalize_text(item.name)]
        if "rest" in latest_norm:
            current = [item for item in current if "rest" not in normalize_text(item.name)]
    additions = retriever.items_by_names(_intended_assessments(all_user_text + "\n" + latest_norm))
    current = unique_items([*current, *additions])
    current = [item for item in current if item.url not in excluded]
    return current[:MAX_RECOMMENDATIONS]


def _intended_assessments(text: str) -> list[str]:
    norm = normalize_text(text)
    names: list[str] = []

    def add(name: str) -> None:
        if name not in names:
            names.append(name)

    if "java" in norm:
        if _contains_any(norm, ["senior", "advanced", "5+", "microservice", "architecture"]):
            add("Core Java (Advanced Level) (New)")
        elif "entry" in norm or "graduate" in norm:
            add("Core Java (Entry Level) (New)")
        else:
            add("Java 8 (New)")
        if "spring" in norm or "backend" in norm:
            add("Spring (New)")
        if "rest" in norm or "api" in norm:
            add("RESTful Web Services (New)")
        if "sql" in norm or "database" in norm:
            add("SQL (New)")
    if "spring" in norm:
        add("Spring (New)")
    if _contains_any(norm, ["sql", "relational database"]):
        add("SQL (New)")
    if _contains_any(norm, ["aws", "amazon web services", "cloud"]):
        add("Amazon Web Services (AWS) Development (New)")
    if "docker" in norm:
        add("Docker (New)")
    if "angular" in norm:
        add("Angular 6 (New)")
    if "rust" in norm or "networking infrastructure" in norm:
        add("Smart Interview Live Coding")
        add("Linux Programming (General)")
        add("Networking and Implementation (New)")
    if (
        ("senior" in norm and _contains_any(norm, ["engineer", "developer", "ic"]))
        or _contains_any(norm, ["architectural", "architecture"])
    ):
        add("SHL Verify Interactive G+")
        add("Occupational Personality Questionnaire OPQ32r")
    if _contains_any(norm, ["excel", "spreadsheet"]):
        add("Microsoft Excel 365 (New)" if "simulation" in norm else "MS Excel (New)")
    if _contains_any(norm, ["word", "document"]):
        if "essential" in norm:
            add("Microsoft Word 365 - Essentials (New)")
        else:
            add("Microsoft Word 365 (New)" if "simulation" in norm else "MS Word (New)")
    if _contains_any(norm, ["contact center", "contact centre", "inbound call", "call center", "customer service"]):
        if _has_any_token(norm, ["us", "u.s", "usa"]) or "no preference" in norm:
            add("SVAR - Spoken English (US) (New)")
        elif _has_any_token(norm, ["uk", "u.k"]):
            add("SVAR - Spoken English (U.K.)")
        elif "australian" in norm or _has_any_token(norm, ["aus"]):
            add("SVAR - Spoken English (AUS)")
        elif "indian" in norm:
            add("SVAR - Spoken English (Indian Accent) (New)")
        add("Contact Center Call Simulation (New)")
        add("Entry Level Customer Serv-Retail & Contact Center")
        add("Customer Service Phone Simulation")
    if _contains_any(norm, ["financial analyst", "finance", "financial accounting"]):
        add("SHL Verify Interactive \u2013 Numerical Reasoning")
        add("Financial Accounting (New)")
        add("Basic Statistics (New)")
        if "graduate" in norm and "drop opq" not in norm and "remove opq" not in norm:
            add("Occupational Personality Questionnaire OPQ32r")
    if "graduate" in norm and _contains_any(norm, ["management", "trainee", "situational", "judgement", "judgment", "scenario"]):
        add("SHL Verify Interactive G+")
        if "drop opq" not in norm and "remove opq" not in norm:
            add("Occupational Personality Questionnaire OPQ32r")
        add("Graduate Scenarios")
    elif _contains_any(norm, ["situational", "judgement", "judgment", "graduate scenarios"]):
        add("Graduate Scenarios")
    if _contains_any(norm, ["senior leadership", "cxo", "director-level", "executive", "leadership benchmark"]):
        add("Occupational Personality Questionnaire OPQ32r")
        add("OPQ Universal Competency Report 2.0")
        add("OPQ Leadership Report")
    if _contains_any(norm, ["sales organization", "sales organisation", "sales audit", "re-skill", "reskill"]):
        add("Global Skills Assessment")
        add("Global Skills Development Report")
        add("Occupational Personality Questionnaire OPQ32r")
        add("OPQ MQ Sales Report")
        add("Sales Transformation 2.0 - Individual Contributor")
    if _contains_any(norm, ["plant operator", "chemical facility", "safety", "dependability", "procedure compliance"]):
        add("Dependability and Safety Instrument (DSI)")
        add("Manufac. & Indust. - Safety & Dependability 8.0")
        add("Workplace Health and Safety (New)")
    if _contains_any(norm, ["healthcare", "hipaa", "medical terminology", "patient records"]):
        add("HIPAA (Security)")
        add("Medical Terminology (New)")
        add("Microsoft Word 365 - Essentials (New)")
        add("Dependability and Safety Instrument (DSI)")
        add("Occupational Personality Questionnaire OPQ32r")
    if _contains_any(norm, ["personality", "behavior", "behaviour", "stakeholder", "mentor"]) and "drop personality" not in norm:
        add("Occupational Personality Questionnaire OPQ32r")
    if _contains_any(norm, ["cognitive", "ability", "g+"]) or ("reasoning" in norm and "numerical" not in norm):
        add("SHL Verify Interactive G+")
    if "numerical" in norm:
        add("SHL Verify Interactive \u2013 Numerical Reasoning")
    return names


def _excluded_assessments(text: str) -> list[str]:
    norm = normalize_text(text)
    excluded: list[str] = []

    def add(name: str) -> None:
        if name not in excluded:
            excluded.append(name)

    if _contains_any(norm, ["drop rest", "remove rest", "exclude rest", "skip rest"]):
        add("RESTful Web Services (New)")
    if _contains_any(norm, ["drop opq", "remove opq", "exclude opq", "skip opq", "drop personality", "skip personality"]):
        add("Occupational Personality Questionnaire OPQ32r")
    if _contains_any(norm, ["drop verify", "remove verify", "skip cognitive", "drop cognitive"]):
        add("SHL Verify Interactive G+")
    return excluded


def _expanded_query(text: str) -> str:
    norm = normalize_text(text)
    additions: list[str] = []
    if "java" in norm:
        additions.append("core java oop generics collections threads concurrency spring sql backend")
    if "admin" in norm:
        additions.append("microsoft office excel word typing administrative")
    if "contact" in norm or "customer service" in norm:
        additions.append("spoken language call simulation customer service contact center")
    if "sales" in norm:
        additions.append("sales transformation global skills opq sales report")
    if "graduate" in norm:
        additions.append("graduate reasoning scenarios numerical personality")
    if "safety" in norm:
        additions.append("dependability safety workplace health")
    return text + "\n" + " ".join(additions)


def _recommendation_intro(latest_norm: str, items: list[CatalogItem]) -> str:
    if "job description" in latest_norm or "jd" in latest_norm:
        prefix = "Based on the job description, here is a grounded SHL shortlist: "
    else:
        prefix = "Here is a grounded SHL shortlist from the catalog: "
    return prefix + _name_sentence(items)


def _contains_any(text: str, terms: list[str]) -> bool:
    return any(term in text for term in terms)


def _has_any_token(text: str, terms: list[str]) -> bool:
    tokens = set(text.split())
    return any(term in tokens for term in terms)
