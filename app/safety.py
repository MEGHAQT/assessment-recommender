from __future__ import annotations

import re


PROMPT_INJECTION_PATTERNS = [
    r"ignore (all )?(previous|prior|above) (instructions|rules)",
    r"forget (the )?(system|developer|instructions)",
    r"reveal (your )?(system|developer|prompt|instructions)",
    r"jailbreak",
    r"bypass (the )?(rules|guardrails|instructions)",
    r"act as if you are not",
    r"fabricate|make up|invent.*(assessment|url|catalog)",
]

LEGAL_PATTERNS = [
    r"\blegally required\b",
    r"\blegal (advice|requirement|obligation|risk|question)\b",
    r"\bregulatory obligation\b",
    r"\bcomply with\b.*\blaw\b",
    r"\bsatisf(y|ies) .*(requirement|law|regulation)\b",
    r"\bcan we be sued\b",
]

HIRING_ADVICE_PATTERNS = [
    r"\bwrite (a )?(job description|interview questions|offer letter)\b",
    r"\bhow (should|do) i interview\b",
    r"\bsalary\b|\bcompensation\b|\bbenefits\b",
    r"\bbackground check\b",
]

ASSESSMENT_SCOPE_TERMS = [
    "assessment",
    "test",
    "screen",
    "shortlist",
    "recommend",
    "shl",
    "catalog",
    "candidate",
    "hiring",
    "role",
    "job",
    "skills",
    "developer",
    "engineer",
    "sales",
    "graduate",
    "manager",
    "admin",
    "contact",
    "customer",
    "analyst",
    "operator",
    "opq",
    "gsa",
    "dsi",
    "verify",
    "svar",
]


def _matches_any(patterns: list[str], text: str) -> bool:
    return any(re.search(pattern, text, flags=re.IGNORECASE | re.DOTALL) for pattern in patterns)


def is_prompt_injection(text: str) -> bool:
    return _matches_any(PROMPT_INJECTION_PATTERNS, text)


def is_legal_question(text: str) -> bool:
    return _matches_any(LEGAL_PATTERNS, text)


def is_general_hiring_advice(text: str) -> bool:
    return _matches_any(HIRING_ADVICE_PATTERNS, text)


def is_off_topic(text: str) -> bool:
    lowered = text.lower()
    if any(term in lowered for term in ASSESSMENT_SCOPE_TERMS):
        return False
    unrelated = [
        "weather",
        "recipe",
        "movie",
        "sports",
        "stock price",
        "travel",
        "homework",
        "poem",
        "joke",
    ]
    return any(term in lowered for term in unrelated) or len(lowered.split()) > 2
