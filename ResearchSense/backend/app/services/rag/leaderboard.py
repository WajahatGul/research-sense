"""Aggregate / leaderboard fast path.

Superlative questions ("who has the most citations", "top researchers by
publications", "most prolific faculty") cannot be answered reliably by
retrieval: the pipeline only sees a handful of chunks, so the model picks a
number it happens to see rather than the true maximum over everyone. These are
answered here directly from the full, sorted structured data.
"""

from __future__ import annotations

import re

from app.services.rag.authored import AuthoredResult, _resolve_people, _Store

_SUPERLATIVE = re.compile(
    r"\b(most|highest|top|leading|greatest|maximum|max|best|"
    r"prolific|productive|ranked|ranking|rank)\b",
    re.I,
)
_CITATION = re.compile(r"\b(citation|citations|cited)\b", re.I)
# What the question ranks. "Which department has the most publications?" used
# to be answered with a researcher's name, because the superlative matched and
# nothing checked what was being compared.
_BY_DEPARTMENT = re.compile(r"\bdepartments?\b", re.I)
_BY_CAMPUS = re.compile(r"\bcampus(?:es)?\b", re.I)
_PUBLICATION = re.compile(
    r"\b(publication|publications|papers?|prolific|productive)\b", re.I
)


def _group_totals(field: str) -> dict[str, dict[str, int]]:
    """Publications and citations per department (or campus).

    A paper is credited once to each group that contributed an author, so the
    totals answer "how much work does this department appear on" rather than
    splitting fractional credit — the question people actually ask. Counting
    each paper once per group also avoids the double counting that summing
    per-researcher totals would produce for internal collaborations.
    """
    group_of = {
        r["researcher_id"]: (r.get(field) or "").strip()
        for r in _Store.researchers()
        if (r.get(field) or "").strip()
    }
    totals: dict[str, dict[str, int]] = {}
    for pub in _Store.pubs():
        groups = {
            group_of[a["researcher_id"]]
            for a in pub.get("authors", [])
            if a.get("researcher_id") in group_of
        }
        cites = int(pub.get("citation_count") or 0)
        for g in groups:
            row = totals.setdefault(g, {"publications": 0, "citations": 0})
            row["publications"] += 1
            row["citations"] += cites
    return totals


def _group_leaderboard(field: str, plural: str, unit: str) -> AuthoredResult | None:
    totals = _group_totals(field)
    if not totals:
        return None
    ranked = sorted(totals.items(), key=lambda kv: -kv[1][unit])[:5]
    best, best_row = ranked[0]
    lines = [
        f"{best} has the most {unit} ({best_row[unit]:,} {unit}).",
        "",
        f"Top {plural} by {unit}:",
    ]
    for i, (name, row) in enumerate(ranked, 1):
        lines.append(f"{i}. {name} - {row[unit]:,} {unit}")
    # No researcher profiles to cite: the answer is about groups, not people.
    return AuthoredResult(answer="\n".join(lines), researchers=[])


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

    unit = "citations" if wants_cite else "publications"

    # Rank what the question actually compares.
    if _BY_DEPARTMENT.search(lower):
        return _group_leaderboard("department", "departments", unit)
    if _BY_CAMPUS.search(lower):
        return _group_leaderboard("campus", "campuses", unit)

    key = "citation_count" if wants_cite else "publication_count"
    researchers = [r for r in _Store.researchers() if r.get(key)]
    if not researchers:
        return None
    ranked = sorted(researchers, key=lambda r: r.get(key, 0), reverse=True)[:5]
    top = ranked[0]

    lines = [
        f"{top['full_name']} has the most {unit} ({top.get(key, 0):,} {unit}).",
        "",
    ]
    lines.append(f"Top researchers by {unit}:")
    for i, r in enumerate(ranked, 1):
        lines.append(f"{i}. {r['full_name']} - {r.get(key, 0):,} {unit}")

    return AuthoredResult(
        answer="\n".join(lines),
        researchers=[(r["full_name"], r["researcher_id"]) for r in ranked],
    )
