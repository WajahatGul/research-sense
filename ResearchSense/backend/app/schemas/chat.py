"""Chatbot (RAG shell) schemas."""
from __future__ import annotations

from pydantic import BaseModel


class ChatRequest(BaseModel):
    """Inbound user question for the assistant."""

    message: str


class ChatSource(BaseModel):
    """A retrieved item cited in the assistant's answer."""

    label: str
    kind: str  # researcher | publication | topic | project
    ref_id: int | None = None


class ChatResponse(BaseModel):
    """Assistant answer plus the sources it drew on."""

    answer: str
    sources: list[ChatSource] = []
