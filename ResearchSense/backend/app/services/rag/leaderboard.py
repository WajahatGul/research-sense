"""Aggregate / leaderboard fast path.

Superlative questions ("who has the most citations", "top researchers by
publications", "most prolific faculty") cannot be answered reliably by
retrieval: the pipeline only sees a handful of chunks, so the model picks a
number it happens to see rather than the true maximum over everyone. These are
answered here directly from the full, sorted structured data.
"""
from __future__ import annotations

import re

from app.services.rag.authored import AuthoredResult, _Store, _resolve_people

_SUPERLATIVE = re.compile(
    r"\b(most|highest|top|leading|greatest|maximum|max|best|"
    r"prolific|productive|ranked|ranking|rank)\b", re.I)
_CITATION = re.compile(r"\b(citation|citations|cited)\b", re.I)
_PUBLICATION = re.compile(
    r"\b(publication|publications|papers?|prolific|productive)\b", re.I)


def leaderboard_answer(message: str) -> AuthoredResult | None:
    """Answer researcher leaderboard questions, else None to fall through."""
    lower = message.lower()
    if not _SUPERLATIVE.search(lower):
        return None
    wants_cite = bool(_CITATION.search(lower))
    wants_pub = bool(_PUBLICATION.search(lower))
    if not (wants_cite or wants_pub):
        return None
    # A specific person named -> not an all-researcher leaderboard; let the
    # person-specific paths / RAG handle it (e.g. "most cited paper by X").
    if _resolve_people(message):
        return None

    key = "citation_count" if wants_cite else "publication_count"
    unit = "citations" if wants_cite else "publications"
    researchers = [r for r in _Store.researchers() if r.get(key)]
    if not researchers:
        return None
    ranked = sorted(researchers, key=lambda r: r.get(key, 0), reverse=True)[:5]
    top = ranked[0]

    lines = [f"{top['full_name']} has the most {unit} "
             f"({top.get(key, 0):,} {unit}).", ""]
    lines.append(f"Top researchers by {unit}:")
    for i, r in enumerate(ranked, 1):
        lines.append(f"{i}. {r['full_name']} - {r.get(key, 0):,} {unit}")

    return AuthoredResult(
        answer="\n".join(lines),
        researchers=[(r["full_name"], r["researcher_id"]) for r in ranked],
    )
