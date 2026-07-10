"""Authored-papers fast path.

Questions like "what papers has Dr. X written?" / "what did X publish?" are
authorship lookups, not semantic search. Answering them from the full-text RAG
index is unreliable: a downloaded paper that merely *mentions* a researcher (as
a co-author on an unrelated work, a citation, or a same-name collision) gets
retrieved and mistaken for their own work.

This module answers such questions directly from the structured publications
data — the same authoritative source the researcher profile page uses — so the
chatbot's list matches the profile exactly. Anything that isn't a clean
authorship question falls through to the normal agentic RAG pipeline.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parents[2] / "data"

# Transliteration variants (kept in sync with retriever._NAME_VARIANTS) so
# "Arif ur Rehman" in a question matches "Arif Ur Rahman" in the data.
_NAME_VARIANTS = {
    "rehman": "rahman", "rahmaan": "rahman",
    "mohammad": "muhammad", "mohammed": "muhammad", "muhammed": "muhammad",
    "muhammd": "muhammad", "mohd": "muhammad",
    "syed": "syed", "sayed": "syed", "sayyed": "syed",
    "hussain": "hussain", "husain": "hussain", "hussein": "hussain",
    "usman": "usman", "othman": "usman", "uthman": "usman",
    "fatima": "fatima", "fatimah": "fatima",
    "ali": "ali", "aly": "ali",
}

# Titles/honorifics stripped before name matching.
_TITLES = r"(?:dr|mr|ms|mrs|prof|professor|engr|sir|madam)\.?\s+"

# The question must look like an authorship request AND name a person for the
# fast path to fire. Kept narrow so content questions ("what does the BERT
# paper say") do not route here.
_AUTHORED_PATTERNS = [
    r"\bwhat\s+papers?\b.*\b(has|did|by|written|authored|published)\b",
    r"\bwhich\s+papers?\b.*\b(has|did|by|written|authored|published)\b",
    r"\b(papers?|publications?|research|work)\b.*\b(written|authored|published)\s+by\b",
    r"\bwhat\s+(did|has)\b.*\b(publish|written|authored)\b",
    r"\blist\b.*\b(papers?|publications?)\b.*\bby\b",
    r"\b(papers?|publications?)\s+of\b",
]


def _norm_name(text: str) -> str:
    tokens = re.findall(r"[a-z]+", text.lower())
    return "".join(_NAME_VARIANTS.get(t, t) for t in tokens)


def is_authored_query(message: str) -> bool:
    """True if the message reads like 'what papers has <person> written'."""
    lower = message.lower()
    return any(re.search(p, lower) for p in _AUTHORED_PATTERNS)


@dataclass
class AuthoredResult:
    answer: str
    researcher_id: int
    researcher_name: str


class _Store:
    """Lazily-loaded, cached researcher + publication tables."""

    _researchers: list[dict] | None = None
    _pubs: list[dict] | None = None

    @classmethod
    def researchers(cls) -> list[dict]:
        if cls._researchers is None:
            cls._researchers = json.loads(
                (DATA_DIR / "researchers.json").read_text("utf-8"))
        return cls._researchers

    @classmethod
    def pubs(cls) -> list[dict]:
        if cls._pubs is None:
            cls._pubs = json.loads(
                (DATA_DIR / "publications.json").read_text("utf-8"))
        return cls._pubs

    @classmethod
    def reset(cls) -> None:
        cls._researchers = None
        cls._pubs = None


def _resolve_researcher(message: str) -> dict | None:
    """Find the researcher whose (title-stripped) name appears in the question.

    Prefers the longest matching name so 'Arif Ur Rahman' wins over a bare
    'Rahman' that could match several people.
    """
    q_norm = _norm_name(message)
    best: dict | None = None
    best_len = 0
    for r in _Store.researchers():
        raw = re.sub(rf"^{_TITLES}", "", r["full_name"].strip(), flags=re.I)
        name_norm = _norm_name(raw)
        # Require a reasonably long full-name match so a common single token
        # doesn't produce a false hit; prefer the longest match.
        if len(name_norm) >= 6 and name_norm in q_norm and len(name_norm) > best_len:
            best, best_len = r, len(name_norm)
    return best


def _publications_for(researcher_id: int) -> list[dict]:
    out = [
        p for p in _Store.pubs()
        if any(a.get("researcher_id") == researcher_id
               for a in p.get("authors", []))
    ]
    # Newest first, then by citations — a stable, sensible order.
    out.sort(key=lambda p: (p.get("publication_year") or 0,
                            p.get("citation_count") or 0), reverse=True)
    return out


def answer(message: str) -> AuthoredResult | None:
    """Return a structured authored-papers answer, or None to fall through."""
    if not is_authored_query(message):
        return None
    researcher = _resolve_researcher(message)
    if researcher is None:
        return None

    rid = researcher["researcher_id"]
    name = researcher["full_name"]
    pubs = _publications_for(rid)

    if not pubs:
        return AuthoredResult(
            answer=(f"I don't have any publications on record for {name} in the "
                    f"ResearchSense database."),
            researcher_id=rid,
            researcher_name=name,
        )

    # Cap very long lists so a prolific author's answer stays readable; the
    # profile page shows the full set.
    LIMIT = 15
    shown = pubs[:LIMIT]

    total = len(pubs)
    header = (f"{name} has {total} publication(s) on record"
              + (f" (showing the {LIMIT} most recent):" if total > LIMIT else ":"))
    lines = [header]
    for p in shown:
        year = p.get("publication_year") or "n.d."
        venue = p.get("journal_name") or ""
        cites = p.get("citation_count") or 0
        sample = " (sample record)" if p.get("source") == "sample" else ""
        tail = f" - {venue}" if venue and venue != "Preprint or unindexed venue" else ""
        lines.append(f"- {p['title']} ({year}){tail}, {cites} citation(s){sample}")
    if total > LIMIT:
        lines.append(f"...and {total - LIMIT} more. See the profile page for the full list.")

    return AuthoredResult(
        answer="\n".join(lines),
        researcher_id=rid,
        researcher_name=name,
    )
