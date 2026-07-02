from __future__ import annotations

from typing import Any

from fastapi import Body, FastAPI

from app.agent import respond
from app.schemas import ChatRequest, ChatResponse


app = FastAPI(title="SHL Assessment Recommender", version="1.0.0")


def _parse_chat_request(payload: object) -> ChatRequest | None:
    try:
        if hasattr(ChatRequest, "model_validate"):
            return ChatRequest.model_validate(payload)
        return ChatRequest.parse_obj(payload)
    except Exception:
        return None


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/chat", response_model=ChatResponse)
def chat(payload: Any = Body(default=None)) -> ChatResponse:
    request = _parse_chat_request(payload)
    if request is None or not request.messages:
        return ChatResponse(
            reply="Please send a messages array with at least one user message about the SHL assessment need.",
            recommendations=[],
            end_of_conversation=False,
        )
    return respond(request.messages)
