"""Department directory fast path.

"Who are the researchers in Computer Science?" / "list the faculty in the
Software Engineering department" are directory lookups, not semantic search.
Retrieval cannot enumerate a department reliably — it only sees a handful of
chunks — so these are answered directly from the structured researcher table,
matching the Researchers page's department filter. Anything that does not
clearly name a known department (a topic question like "who works on machine
learning") falls through to the normal RAG pipeline.
"""

from __future__ import annotations

import re

from app.services.rag.authored import AuthoredResult, _Store

# Common short forms -> a substring of the canonical department name.
_ALIASES = {
    "cs": "computer science",
    "se": "software engineering",
    "ce": "computer engineering",
    "ee": "electrical engineering",
    "hr": "hr and management",
    "ir": "international relations",
}

# A person-noun must appear ("researchers in X"), or a bare "who ... in X".
_PEOPLE_NOUN = re.compile(
    r"\b(researchers?|faculty|staff|professors?|academics?|lecturers?|"
    r"scientists?|teachers?|people|members?|employees?)\b",
    re.I,
)
_WHO_IN = re.compile(r"\bwho\b.*\b(in|from|of|at|part of|belongs? to)\b", re.I)

# "works on / research on <topic>" is a topic question — leave it to RAG, even
# when it also names a department ("ML researchers in Computer Science").
_TOPIC_ON = re.compile(
    r"\b(work|works|working|research|researches|focus|focuses|focusing|"
    r"specialis\w*|specializ\w*|expert)\s+on\b",
    re.I,
)

_MAX = 25


def _departments() -> list[str]:
    return sorted(
        {
            (r.get("department") or "").strip()
            for r in _Store.researchers()
            if r.get("department")
        }
    )


def _resolve_department(message: str) -> str | None:
    """Match a whole-word department name (longest wins) or a known alias."""
    lower = message.lower()
    best: str | None = None
    for dept in _departments():
        if re.search(rf"\b{re.escape(dept.lower())}\b", lower) and (
            best is None or len(dept) > len(best)
        ):
            best = dept
    if best:
        return best
    for alias, canonical in _ALIASES.items():
        if re.search(rf"\b{alias}\b", lower):
            for dept in _departments():
                if canonical in dept.lower():
                    return dept
    return None


def directory_answer(message: str) -> AuthoredResult | None:
    """List the researchers in a named department, else None to fall through."""
    if _TOPIC_ON.search(message):
        return None
    if not (_PEOPLE_NOUN.search(message) or _WHO_IN.search(message)):
        return None
    dept = _resolve_department(message)
    if dept is None:
        return None
    people = [
        r for r in _Store.researchers() if (r.get("department") or "").strip() == dept
    ]
    if not people:
        return None
    people.sort(key=lambda r: (-(r.get("publication_count") or 0), r["full_name"]))
    shown = people[:_MAX]

    n = len(people)
    head = f"{dept} has {n} researcher{'s' if n != 1 else ''} on record"
    head += f" (showing the {len(shown)} most published):" if len(shown) < n else ":"
    lines = [head]
    for r in shown:
        rank = (r.get("academic_rank") or r.get("designation") or "").strip()
        campus = (r.get("campus") or "").strip()
        meta = " · ".join(x for x in (rank, campus) if x)
        lines.append(f"- {r['full_name']}" + (f" — {meta}" if meta else ""))

    return AuthoredResult(
        answer="\n".join(lines),
        researchers=[(r["full_name"], r["researcher_id"]) for r in shown],
    )
