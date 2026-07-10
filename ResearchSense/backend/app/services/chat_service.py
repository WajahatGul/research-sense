"""Grounded RAG chat service.

Pipeline: retrieve → confidence gate → generate → cite. The answer can only
come from indexed ResearchSense data (profiles, publications, projects, topics)
and the downloaded research papers. Questions the index cannot support are
refused honestly; the LLM is never called for them.
"""
from __future__ import annotations

from app.schemas.chat import ChatResponse, ChatSource, ChatTurn
from app.services.rag.generator import REFUSAL_MESSAGE, generate
from app.services.rag.retriever import Retriever, ScoredChunk, is_confident

INDEX_MISSING_MESSAGE = (
    "The assistant's knowledge index has not been built yet. Run "
    "'python -m scripts.build_index' in the backend and try again."
)


def _sources_from(chunks: list[ScoredChunk], limit: int = 5) -> list[ChatSource]:
    """Cited sources come from retrieval, never from the model."""
    sources, seen = [], set()
    for c in chunks:
        if c.label in seen:
            continue
        seen.add(c.label)
        sources.append(ChatSource(label=c.label, kind=c.kind, ref_id=c.ref_id))
        if len(sources) >= limit:
            break
    return sources


def _retrieval_query(question: str, history: list[ChatTurn]) -> str:
    """Fold recent conversation into the search query so follow-ups like
    "explain the full paper in detail" retrieve what the user is referring to.
    """
    recent = [t.content for t in history[-4:]]
    return " ".join(recent + [question]) if recent else question


class ChatService:
    def answer(self, message: str, history: list[ChatTurn] | None = None) -> ChatResponse:
        question = message.strip()
        history = history or []
        if not question:
            return ChatResponse(
                answer="Please ask a question about our researchers, "
                       "publications, projects, or papers.")

        if not Retriever.available():
            return ChatResponse(answer=INDEX_MISSING_MESSAGE)

        results = Retriever.instance().retrieve(_retrieval_query(question, history))

        # Confidence gate: nothing relevant in the index -> refuse, no LLM call.
        if not is_confident(results):
            return ChatResponse(answer=REFUSAL_MESSAGE)

        answer, _used_llm = generate(question, results, history)
        if answer == REFUSAL_MESSAGE:
            return ChatResponse(answer=REFUSAL_MESSAGE)
        return ChatResponse(answer=answer, sources=_sources_from(results))
