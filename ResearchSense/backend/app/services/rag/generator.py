"""Answer generation for the RAG chatbot.

Primary path: Groq free tier (Llama 3.3 70B, temperature 0) with a strict
context-only prompt and a refusal token. Fallback path: a grounded extractive
answer assembled directly from the retrieved chunks, used when no API key is
set or the Groq call fails. Both paths can only speak from retrieved text.
"""
from __future__ import annotations

import httpx

from app.core.config import settings
from app.services.rag.retriever import ScoredChunk

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
REFUSAL_TOKEN = "NO_ANSWER"

REFUSAL_MESSAGE = (
    "I don't have that information in the ResearchSense database. I can only "
    "answer from indexed faculty profiles, publications, projects, and the "
    "research papers in my library."
)

SYSTEM_PROMPT = f"""You are ResearchSense, the research assistant of Bahria University.

Rules you must never break:
1. Answer ONLY from the context provided below. Never use outside knowledge.
2. If the context does not contain the information needed to answer, reply with
   exactly: {REFUSAL_TOKEN}
3. Never guess, estimate, or invent names, numbers, dates, titles, or findings.
4. If a context item is marked as a demonstration record, say so when using it.
5. Be concise and factual. Plain text only, no markdown headings."""


def _format_context(chunks: list[ScoredChunk]) -> str:
    return "\n\n".join(f"[{i + 1}] {c.text}" for i, c in enumerate(chunks))


def generate(question: str, chunks: list[ScoredChunk]) -> tuple[str, bool]:
    """Return (answer, used_llm). Falls back to extractive mode on any failure."""
    if settings.groq_api_key:
        try:
            answer = _groq_answer(question, chunks)
            if answer is not None:
                if REFUSAL_TOKEN in answer:
                    return REFUSAL_MESSAGE, True
                return answer, True
        except httpx.HTTPError:
            pass
    return _extractive_answer(chunks), False


def _groq_answer(question: str, chunks: list[ScoredChunk]) -> str | None:
    response = httpx.post(
        GROQ_URL,
        headers={"Authorization": f"Bearer {settings.groq_api_key}"},
        json={
            "model": settings.groq_model,
            "temperature": 0,
            "max_tokens": 600,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": (
                    f"Context:\n{_format_context(chunks)}\n\n"
                    f"Question: {question}")},
            ],
        },
        timeout=45,
    )
    if response.status_code != 200:
        return None
    content = response.json()["choices"][0]["message"]["content"].strip()
    return content or None


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
