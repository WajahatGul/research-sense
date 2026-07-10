"""Chatbot endpoint (mock RAG shell)."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from app.core.deps import get_chat_service
from app.schemas.chat import ChatRequest, ChatResponse
from app.services.chat_service import ChatService

router = APIRouter(prefix="/api/chat", tags=["chat"])


@router.post("", response_model=ChatResponse)
def ask(
    payload: ChatRequest,
    service: ChatService = Depends(get_chat_service),
):
    return service.answer(payload.message, payload.history)
