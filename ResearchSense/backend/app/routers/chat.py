"""Chatbot endpoint (mock RAG shell)."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.core.deps import get_chat_service
from app.schemas.chat import ChatRequest, ChatResponse
from app.services.chat_service import ChatService
from app.services.suggestion_service import suggestions

router = APIRouter(prefix="/api/chat", tags=["chat"])


@router.post("", response_model=ChatResponse)
def ask(
    payload: ChatRequest,
    service: ChatService = Depends(get_chat_service),
):
    return service.answer(payload.message, payload.history)


@router.get("/suggestions", response_model=list[str])
def starter_questions() -> list[str]:
    """Questions the workspace being served can actually answer.

    Empty for a workspace with no data yet, so the client can invite the
    researcher to add their work instead of offering a dead end.
    """
    return suggestions()
