"""How much is in here: institution-level counts.

"How many publications does Bahria University have?" is the most basic
question anyone asks a research portal, and it used to dead-end. Retrieval
cannot answer it: no single chunk contains the total, so the assistant found
nothing relevant and said so, while the number sat on the home page.

Counted from the structured tables for whichever workspace is being served,
the same source the stats endpoint uses, so the assistant and the pages can
never disagree.
"""

from __future__ import annotations

import re

from app.core.tenancy import institution_name
from app.repositories import loader
from app.services.rag.authored import AuthoredResult, _resolve_people

# "how many", "how much", "number of", "total" — a counting question.
_COUNT_INTENT = re.compile(
    r"\b(how\s+many|how\s+much|number\s+of|total\s+(?:number\s+)?of|count\s+of)\b",
    re.I,
)

# What is being counted. Order matters: the first match wins, and "research
# areas" must beat the bare "research" in a publication question.
_SUBJECTS: list[tuple[str, re.Pattern[str], str]] = [
    (
        "publications",
        re.compile(r"\b(publications?|papers?|articles?|research\s+outputs?)\b", re.I),
        "publications",
    ),
    (
        "researchers",
        re.compile(
            r"\b(researchers?|faculty|staff|academics?|professors?|people)\b", re.I
        ),
        "researchers",
    ),
    (
        "research areas",
        re.compile(r"\b(research\s+areas?|topics?|fields?|disciplines?)\b", re.I),
        "topics",
    ),
    ("projects", re.compile(r"\bprojects?\b", re.I), "projects"),
    ("departments", re.compile(r"\bdepartments?\b", re.I), None),
    ("campuses", re.compile(r"\bcampus(?:es)?\b", re.I), None),
]

# A count scoped to one person or place is a different question, answered
# elsewhere from that record rather than from the institution total.
_SCOPED = re.compile(
    r"\b(in|at|from|for|by|on)\b.*\b(campus|department|karachi|lahore|islamabad)\b",
    re.I,
)


def _counts() -> dict[str, int]:
    researchers = loader.load("researchers")
    curated = [r for r in researchers if not loader.is_extended(r)]
    return {
        "publications": len(loader.load("publications")),
        "researchers": len(curated),
        "topics": len(loader.load("topics")),
        "projects": len(loader.load("projects")),
        "departments": len(
            {
                (r.get("department") or "").strip()
                for r in curated
                if r.get("department")
            }
        ),
        "campuses": len(
            {(r.get("campus") or "").strip() for r in curated if r.get("campus")}
        ),
        "extended": len(researchers) - len(curated),
    }


def totals_answer(message: str) -> AuthoredResult | None:
    """Answer "how many X are there?" about the whole institution."""
    if not _COUNT_INTENT.search(message):
        return None
    if _SCOPED.search(message):
        return None  # a narrower question than this path should answer
    # "How many papers has Nida Aman written?" is a question about her, not
    # about the institution; the authorship path answers it from her record.
    if _resolve_people(message):
        return None

    subject = next(
        ((label, key) for label, pattern, key in _SUBJECTS if pattern.search(message)),
        None,
    )
    if subject is None:
        return None
    label, _key = subject
    counts = _counts()
    n = counts[label.replace("research areas", "topics")]

    owner = institution_name()
    subject_name = owner or "This portal"
    lines = [f"{subject_name} has {n:,} {label} on record in ResearchSense."]

    if label == "researchers" and counts["extended"]:
        lines.append(
            f"That is the directory. A further {counts['extended']:,} authors "
            "appear on indexed papers without a directory profile — search a "
            "name to find them."
        )
    if label == "publications":
        lines.append(
            "Counts reflect what has been matched and indexed so far, so the "
            "real figure is higher."
        )

    return AuthoredResult(answer="\n\n".join(lines), researchers=[])
