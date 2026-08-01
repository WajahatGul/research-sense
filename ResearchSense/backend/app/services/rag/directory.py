"""Directory fast paths: list researchers by department or by research area.

"Who are the researchers in Computer Science?" (a department) and "list
researchers in AI" / "who works on machine learning" (a research area) are
directory lookups, not semantic search. Retrieval cannot enumerate a group
reliably — it only sees a handful of chunks, so wording changes flip a real
answer into a refusal. These are answered directly from the structured
researcher table, matching the Researchers / Research Areas pages. Questions
that are really about a paper ("who wrote the ML paper") are excluded and left
to the authored / RAG paths.
"""

from __future__ import annotations

import re

from app.services.rag.authored import AuthoredResult, _Store

_MAX = 25

# --- shared rendering -------------------------------------------------------


def _render(header: str, people: list[dict]) -> AuthoredResult:
    people = sorted(
        people, key=lambda r: (-(r.get("publication_count") or 0), r["full_name"])
    )
    shown = people[:_MAX]
    lines = [header]
    for r in shown:
        rank = (r.get("academic_rank") or r.get("designation") or "").strip()
        campus = (r.get("campus") or "").strip()
        meta = " · ".join(x for x in (rank, campus) if x)
        lines.append(f"- **{r['full_name']}**" + (f" — {meta}" if meta else ""))
    return AuthoredResult(
        answer="\n".join(lines),
        researchers=[(r["full_name"], r["researcher_id"]) for r in shown],
    )


def _count_tail(total: int, shown: int) -> str:
    return f" (showing the {shown} most published):" if shown < total else ":"


# --- department directory ---------------------------------------------------

_ALIASES = {
    "cs": "computer science",
    "se": "software engineering",
    "ce": "computer engineering",
    "ee": "electrical engineering",
    "hr": "hr and management",
    "ir": "international relations",
}

_PEOPLE_NOUN = re.compile(
    r"\b(researchers?|faculty|staff|professors?|academics?|lecturers?|"
    r"scientists?|teachers?|people|members?|employees?|experts?|specialists?)\b",
    re.I,
)
_WHO_IN = re.compile(r"\bwho\b.*\b(in|from|of|at|part of|belongs? to)\b", re.I)

# "works on / research on <topic>" is a research-area question — handled by
# research_area_answer, not the department path.
_TOPIC_ON = re.compile(
    r"\b(work|works|working|research|researches|focus|focuses|focusing|"
    r"specialis\w*|specializ\w*|expert)\s+on\b",
    re.I,
)


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
    n = len(people)
    header = (
        f"{dept} has {n} researcher{'s' if n != 1 else ''} on record"
        + _count_tail(n, min(n, _MAX))
    )
    return _render(header, people)


# --- research-area directory ------------------------------------------------

# Short forms so a terse query resolves ("ai" -> "artificial intelligence").
_AREA_SYNONYMS = {
    "ai": "artificial intelligence",
    "ml": "machine learning",
    "dl": "deep learning",
    "nlp": "natural language processing",
    "cv": "computer vision",
    "iot": "internet of things",
    "hci": "human computer interaction",
    "ar": "augmented reality",
    "vr": "virtual reality",
    "cybersecurity": "cyber security",
    "infosec": "information security",
}

# A paper/authorship question is not a "list people in this area" question.
_AREA_EXCLUDE = re.compile(
    r"\b(paper|papers|publication|publications|wrote|written|authored|"
    r"cite|cited|citation)\b",
    re.I,
)


def _known_areas() -> list[str]:
    """Every research area / topic name in the data, longest first so the most
    specific phrase wins (e.g. 'Machine Learning' over 'Learning')."""
    areas: set[str] = set()
    for r in _Store.researchers():
        for a in r.get("research_areas") or []:
            if a and len(a.strip()) >= 3:
                areas.add(a.strip())
        for t in r.get("topics") or []:
            name = t.get("topic_name") if isinstance(t, dict) else None
            if name and len(name.strip()) >= 3:
                areas.add(name.strip())
    return sorted(areas, key=len, reverse=True)


def _resolve_area(message: str) -> str | None:
    lower = message.lower()
    expanded = lower
    for abbr, full in _AREA_SYNONYMS.items():
        if re.search(rf"\b{re.escape(abbr)}\b", lower):
            expanded += " " + full
    tokens = set(re.findall(r"[a-z]+", expanded))
    for area in _known_areas():
        al = area.lower()
        words = al.split()
        hit = (al in tokens) if len(words) == 1 else (al in expanded)
        if hit:
            return area
    return None


def _in_area(researcher: dict, area_lower: str) -> bool:
    for a in researcher.get("research_areas") or []:
        if a and a.lower() == area_lower:
            return True
    for t in researcher.get("topics") or []:
        name = t.get("topic_name") if isinstance(t, dict) else None
        if name and name.lower() == area_lower:
            return True
    return False


def research_area_answer(message: str) -> AuthoredResult | None:
    """List researchers who work in a named research area, else None.

    Fixes false refusals where retrieval scored a real topic question (e.g.
    "list researchers in AI") just below the confidence bar even though the data
    clearly has the answer.
    """
    if _AREA_EXCLUDE.search(message):
        return None
    if not (_PEOPLE_NOUN.search(message) or re.search(r"\bwho\b", message, re.I)):
        return None
    area = _resolve_area(message)
    if area is None:
        return None
    area_lower = area.lower()
    people = [r for r in _Store.researchers() if _in_area(r, area_lower)]
    if not people:
        return None
    n = len(people)
    header = f"{n} researcher{'s' if n != 1 else ''} work on {area}" + _count_tail(
        n, min(n, _MAX)
    )
    return _render(header, people)
