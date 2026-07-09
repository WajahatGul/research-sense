"""Mock RAG chatbot service.

Phase 1 does simple keyword retrieval over researchers/topics and composes a
templated answer. The real RAG pipeline replaces the body of ``answer`` without
changing the interface.
"""
from __future__ import annotations

from app.repositories.base import ResearcherRepository, TopicRepository
from app.schemas.chat import ChatResponse, ChatSource

_STOPWORDS = {
    "who", "what", "which", "show", "find", "list", "the", "a", "an", "on",
    "in", "of", "for", "me", "is", "are", "works", "working", "work", "at",
    "about", "research", "researcher", "researchers", "and", "to", "with",
}


def _keywords(message: str) -> set[str]:
    tokens = "".join(c.lower() if c.isalnum() else " " for c in message).split()
    return {t for t in tokens if t not in _STOPWORDS and len(t) > 2}


class ChatService:
    def __init__(self, researchers: ResearcherRepository, topics: TopicRepository):
        self._researchers = researchers
        self._topics = topics

    def answer(self, message: str) -> ChatResponse:
        msg = message.strip()
        if not msg:
            return ChatResponse(answer="Please ask a question about our research.")

        lower = msg.lower()
        words = _keywords(msg)

        # A topic matches when its name (or a keyword of it) is mentioned.
        matched_topics = [
            t for t in self._topics.list()
            if t.topic_name.lower() in lower
            or bool(_keywords(t.topic_name) & words)
        ][:3]

        researchers = self._find_researchers(matched_topics, words)
        sources: list[ChatSource] = []
        for r in researchers:
            sources.append(ChatSource(
                label=f"{r.full_name} — {r.designation}",
                kind="researcher", ref_id=r.researcher_id,
            ))
        for t in matched_topics:
            sources.append(ChatSource(
                label=t.topic_name, kind="topic", ref_id=t.topic_id,
            ))

        return ChatResponse(
            answer=self._compose(msg, researchers, matched_topics),
            sources=sources,
        )

    def _find_researchers(self, matched_topics, words):
        topic_ids = {t.topic_id for t in matched_topics}
        matched = []
        for r in self._researchers.list():
            in_topic = any(rt.topic_id in topic_ids for rt in r.topics)
            in_name = bool(_keywords(r.full_name) & words)
            if in_topic or in_name:
                matched.append(r)
        matched.sort(key=lambda r: r.citation_count, reverse=True)
        return matched[:4]

    @staticmethod
    def _compose(msg, researchers, topics) -> str:
        if researchers:
            names = ", ".join(r.full_name for r in researchers)
            area = f" working on {topics[0].topic_name}" if topics else ""
            return (
                f"At Bahria University (E-8), researchers{area} include {names}. "
                "Open a profile to see publications and collaboration options."
            )
        if topics:
            areas = ", ".join(t.topic_name for t in topics)
            return (
                f"That relates to research areas: {areas}. Browse the Topics "
                "section to explore contributing researchers."
            )
        return (
            "I could not find a direct match yet. Try a researcher name, a "
            "department, or a research area such as 'machine learning', "
            "'cybersecurity', or 'internet of things'."
        )
