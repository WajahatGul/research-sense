"""Grounded RAG chat service.

Pipeline: retrieve → confidence gate → generate → cite. The answer can only
come from indexed ResearchSense data (profiles, publications, projects, topics)
and the downloaded research papers. Questions the index cannot support are
refused honestly; the LLM is never called for them.
"""

from __future__ import annotations

from app.core.config import settings
from app.schemas.chat import ChatResponse, ChatSource, ChatTurn
from app.services.rag import authored
from app.services.rag.agentic import normalize_query
from app.services.rag.directory import directory_answer, research_area_answer
from app.services.rag.generator import REFUSAL_MESSAGE, generate, grounded_facts
from app.services.rag.leaderboard import leaderboard_answer
from app.services.rag.retriever import Retriever, ScoredChunk, is_confident

# Shown when the semantic index is missing — a brand-new institution
# workspace has none until its own records are indexed. The structured fast
# paths above still work, so this names what the assistant *can* answer today
# rather than showing a build command to someone who cannot run one.
INDEX_MISSING_MESSAGE = (
    "I do not have a searchable index of this workspace's records yet, so I "
    "cannot answer open-ended questions here. I can still answer directly from "
    "your saved data — for example who works in a department or research area, "
    "what a researcher has published, or who has the most publications. Adding "
    "your profile and papers on the portal builds the index for everything else."
)

# Shown when nothing meaningfully related was found. A helpful redirect rather
# than a dead end, so a question never ends in a blunt wall.
NO_MATCH_MESSAGE = (
    "I could not find anything on that in the records I have indexed so far, "
    "which cover faculty profiles, publications, projects, and the papers in "
    "the library. You could try rephrasing the question, browsing the "
    "Researchers or Research Areas pages, or asking about a specific person, "
    "topic, or paper."
)

# Appended when the answer rests on weak evidence, so the reader knows the
# coverage is limited without the assistant either guessing or refusing.
LIMITED_COVERAGE_NOTE = (
    "Note: this reflects only the records ResearchSense has indexed so far, so "
    "the coverage may be incomplete. The Researchers and Research Areas pages "
    "show the full indexed set."
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
    def answer(
        self, message: str, history: list[ChatTurn] | None = None
    ) -> ChatResponse:
        question = message.strip()
        history = history or []
        if not question:
            return ChatResponse(
                answer="Please ask a question about our researchers, "
                "publications, projects, or papers."
            )

        # Pass 0: resolve a contextual follow-up ("and how?", "is it related to
        # AI?", "what did he write?") into a self-contained question using the
        # recent conversation, before any routing or retrieval. No-op on the
        # first turn (no history) or when normalization is unavailable.
        history_dicts = [
            {"role": t.role, "content": t.content}
            for t in history
            if t.role in ("user", "assistant")
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
                    ChatSource(label=f"{name} — profile", kind="researcher", ref_id=rid)
                    for name, rid in collab_result.researchers
                ],
            )

        # Fast path: superlative/leaderboard questions ("who has the most
        # citations", "top researchers by publications") — answered from the
        # full sorted data, since retrieval only sees a few chunks and would
        # pick a wrong maximum.
        board = leaderboard_answer(question)
        if board is not None:
            return ChatResponse(
                answer=board.answer,
                sources=[
                    ChatSource(label=f"{name} — profile", kind="researcher", ref_id=rid)
                    for name, rid in board.researchers
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
                    ChatSource(label=f"{name} — profile", kind="researcher", ref_id=rid)
                    for name, rid in authored_result.researchers
                ],
            )

        # Fast path: "who are the researchers in <department>?" is a directory
        # listing, answered from the structured table (matching the Researchers
        # page filter) rather than retrieval, which only sees a few chunks and
        # would refuse or under-list. Topic questions ("who works on X") are
        # excluded by directory_answer and handled by RAG below.
        directory = directory_answer(question)
        if directory is not None:
            return ChatResponse(
                answer=directory.answer,
                sources=[
                    ChatSource(label=f"{name} — profile", kind="researcher", ref_id=rid)
                    for name, rid in directory.researchers
                ],
            )

        # Fast path: "list researchers in AI" / "who works on machine learning"
        # is a research-area lookup. Retrieval scores terse topic questions
        # inconsistently (a real answer can fall just below the confidence bar
        # and get refused), so answer these deterministically from the
        # structured research-area data. Paper/authorship questions are excluded.
        area = research_area_answer(question)
        if area is not None:
            return ChatResponse(
                answer=area.answer,
                sources=[
                    ChatSource(label=f"{name} — profile", kind="researcher", ref_id=rid)
                    for name, rid in area.researchers
                ],
            )

        # Everything past here is semantic search. The fast paths above read the
        # structured tables directly, so they answer for a workspace whose index
        # has not been built yet; only this part needs one.
        if not Retriever.available():
            return ChatResponse(answer=INDEX_MISSING_MESSAGE)

        results = Retriever.instance().retrieve(_retrieval_query(question, history))
        top = results[0].score if results else 0.0

        # Nothing meaningfully related: give a helpful redirect (never a blunt
        # dead end), and skip the model call.
        if top < settings.rag_soft_threshold:
            return ChatResponse(answer=NO_MATCH_MESSAGE)

        answer, used_llm = generate(question, results, history)

        # The model read the passages and judged they do not answer the
        # question (e.g. an out-of-scope question that only shares a stray
        # keyword): redirect helpfully rather than dumping loosely-matched text.
        if used_llm and answer == REFUSAL_MESSAGE:
            return ChatResponse(answer=NO_MATCH_MESSAGE)

        # Model unavailable (no key or every model exhausted): fall back to the
        # grounded facts so the user still gets something concrete.
        if not answer:
            answer = grounded_facts(results)

        # Weak evidence (below the strong-confidence bar): keep the answer but
        # add a professional note that the coverage is limited.
        if not is_confident(results):
            answer = answer.rstrip() + "\n\n" + LIMITED_COVERAGE_NOTE

        return ChatResponse(answer=answer, sources=_sources_from(results))
