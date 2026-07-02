from app.llm import augment_search_text, llm_enabled
from app.schemas import Message


def test_llm_disabled_without_key(monkeypatch) -> None:
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("DISABLE_LLM", raising=False)
    assert llm_enabled() is False


def test_llm_augment_search_text_uses_gemini_when_configured(monkeypatch) -> None:
    monkeypatch.setenv("DISABLE_LLM", "0")
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setattr("app.llm._call_gemini", lambda prompt: "senior backend java spring sql aws docker")

    text = augment_search_text(
        [Message(role="user", content="Here is a messy job description for a platform role.")],
        "original query",
    )

    assert "original query" in text
    assert "LLM intent summary" in text
    assert "senior backend java" in text
