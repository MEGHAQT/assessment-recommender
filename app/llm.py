from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

from app.schemas import Message


GEMINI_INTERACTIONS_URL = "https://generativelanguage.googleapis.com/v1beta/interactions"
DEFAULT_GEMINI_MODEL = "gemini-3.5-flash"
DEFAULT_TIMEOUT_SECONDS = 6.0


def llm_enabled() -> bool:
    disabled = os.getenv("DISABLE_LLM", "").strip().lower()
    if disabled in {"1", "true", "yes"}:
        return False
    return bool(os.getenv("GEMINI_API_KEY", "").strip())


def augment_search_text(messages: list[Message], fallback_text: str) -> str:
    """Add an LLM intent summary to the retrieval query when Gemini is configured."""
    if not llm_enabled():
        return fallback_text

    prompt = _intent_prompt(messages)
    summary = _call_gemini(prompt)
    if not summary:
        return fallback_text
    return f"{fallback_text}\n\nLLM intent summary:\n{summary}"


def _intent_prompt(messages: list[Message]) -> str:
    rendered = []
    for message in messages[-8:]:
        content = " ".join(message.content.split())
        if len(content) > 2500:
            content = content[:2500] + " ..."
        rendered.append(f"{message.role}: {content}")

    conversation = "\n".join(rendered)
    return (
        "You extract search intent for an SHL assessment recommender. "
        "Return one compact plain-text line only. Do not recommend products, invent catalog names, or include URLs. "
        "Capture role, seniority, skills, domain, language/accent, cognitive/personality/simulation needs, "
        "duration constraints, and requested additions or exclusions.\n\n"
        f"Conversation:\n{conversation}"
    )


def _call_gemini(prompt: str) -> str | None:
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        return None

    model = os.getenv("GEMINI_MODEL", DEFAULT_GEMINI_MODEL).strip() or DEFAULT_GEMINI_MODEL
    timeout = _timeout_seconds()
    payload = {
        "model": model,
        "store": False,
        "input": prompt,
    }
    request = urllib.request.Request(
        GEMINI_INTERACTIONS_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "x-goog-api-key": api_key,
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            data = json.loads(response.read().decode("utf-8"))
    except (OSError, TimeoutError, urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError):
        return None

    text = _extract_text(data)
    if not text:
        return None
    return " ".join(text.split())[:1200]


def _timeout_seconds() -> float:
    try:
        return max(1.0, float(os.getenv("LLM_TIMEOUT_SECONDS", str(DEFAULT_TIMEOUT_SECONDS))))
    except ValueError:
        return DEFAULT_TIMEOUT_SECONDS


def _extract_text(data: object) -> str:
    if not isinstance(data, dict):
        return ""
    output_text = data.get("output_text")
    if isinstance(output_text, str):
        return output_text

    chunks: list[str] = []
    for step in data.get("steps", []):
        if not isinstance(step, dict):
            continue
        for part in step.get("content", []):
            if isinstance(part, dict) and isinstance(part.get("text"), str):
                chunks.append(part["text"])
    return " ".join(chunks)
