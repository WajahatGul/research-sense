"""Grounded RAG chat service.

Pipeline: retrieve → confidence gate → generate → cite. The answer can only
come from indexed ResearchSense data (profiles, publications, projects, topics)
and the downloaded research papers. Questions the index cannot support are
refused honestly; the LLM is never called for them.
"""
from __future__ import annotations

from app.schemas.chat import ChatResponse, ChatSource, ChatTurn
from app.services.rag import authored
from app.services.rag.agentic import normalize_query
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

        # Pass 0: resolve a contextual follow-up ("and how?", "is it related to
        # AI?", "what did he write?") into a self-contained question using the
        # recent conversation, before any routing or retrieval. No-op on the
        # first turn (no history) or when normalization is unavailable.
        history_dicts = [
            {"role": t.role, "content": t.content}
            for t in history if t.role in ("user", "assistant")
        ]
        question = normalize_query(question, history_dicts)

        # Fast path: "did X and Y collaborate / write together" is a two-person
        # co-authorship lookup — answered precisely from shared publications
        # (or an honest "they haven't, but share these areas"). Checked before
        # the single-author path, which would otherwise misfire on one name.
        collab_result = authored.collaboration_answer(question)
        if collab_result is not None:
            return ChatResponse(
                answer=collab_result.answer,
                sources=[
                    ChatSource(label=f"{name} — profile",
                               kind="researcher", ref_id=rid)
                    for name, rid in collab_result.researchers
                ],
            )

        # Fast path: "what papers has X written?" is an authorship lookup, best
        # answered from the structured publications table (matching the profile
        # page) rather than fuzzy full-text retrieval, which conflates papers
        # that merely mention the name with papers the person actually wrote.
        authored_result = authored.answer(question, history)
        if authored_result is not None:
            return ChatResponse(
                answer=authored_result.answer,
                sources=[
                    ChatSource(label=f"{name} — profile",
                               kind="researcher", ref_id=rid)
                    for name, rid in authored_result.researchers
                ],
            )

        results = Retriever.instance().retrieve(_retrieval_query(question, history))

        # Confidence gate: nothing relevant in the index -> refuse, no LLM call.
        if not is_confident(results):
            return ChatResponse(answer=REFUSAL_MESSAGE)

        answer, _used_llm = generate(question, results, history)
        if answer == REFUSAL_MESSAGE:
            return ChatResponse(answer=REFUSAL_MESSAGE)
        return ChatResponse(answer=answer, sources=_sources_from(results))
