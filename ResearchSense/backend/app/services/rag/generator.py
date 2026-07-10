"""Answer generation for the RAG chatbot.

Primary path: a multi-pass **agentic pipeline** (intent -> evidence -> synthesis)
that walks a chain of high-quality Groq models with multi-key rate-limit
failover — see ``app.services.rag.agentic``. Fallback path: a grounded
extractive answer assembled directly from the retrieved chunks, used when no
API key is set or every model call fails. Both paths can only speak from
retrieved text.
"""
from __future__ import annotations

from app.services.rag import agentic
from app.services.rag.retriever import ScoredChunk

REFUSAL_TOKEN = agentic.REFUSAL_TOKEN

REFUSAL_MESSAGE = (
    "I don't have that information in the ResearchSense database. I can only "
    "answer from indexed faculty profiles, publications, projects, and the "
    "research papers in my library."
)


def generate(question: str, chunks: list[ScoredChunk],
             history: list | None = None) -> tuple[str, bool]:
    """Return (answer, used_llm). Falls back to extractive mode on any failure.

    The primary path is the 3-pass agentic pipeline. The refusal token from
    Pass 3 maps to the friendly REFUSAL_MESSAGE; an empty result (no key, or
    every model exhausted) degrades to a grounded extractive answer.
    """
    if agentic.available():
        turns = history or []
        conversation_history = [
            {"role": t.role, "content": t.content[:1200]}
            for t in turns if t.role in ("user", "assistant")
        ]
        answer = agentic.run_agentic_pipeline(
            user_message=question,
            retrieved_chunks=chunks,
            conversation_history=conversation_history,
        )
        if answer:
            if REFUSAL_TOKEN in answer:
                return REFUSAL_MESSAGE, True
            return answer, True
    return _extractive_answer(chunks), False


def _extractive_answer(chunks: list[ScoredChunk]) -> str:
    """Grounded fallback: present the retrieved facts directly."""
    lines = ["Here is what the ResearchSense database contains on this:"]
    seen: set[str] = set()
    for c in chunks[:4]:
        snippet = c.text if len(c.text) <= 320 else c.text[:317] + "..."
        if snippet not in seen:
            seen.add(snippet)
            lines.append(f"- {snippet}")
    return "\n".join(lines)
