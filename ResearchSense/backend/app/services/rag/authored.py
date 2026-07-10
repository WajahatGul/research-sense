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
# paper say") do not route here. Tolerates typos in surrounding words and
# words between ("what resarch papers did arif wrote").
_AUTHOR_VERBS = r"(?:wrote|write|written|writes|authored|author|published|publish|publications?)"
_AUTHORED_PATTERNS = [
    rf"\b(what|which)\b.*\bpapers?\b.*\b(has|did|by|{_AUTHOR_VERBS})\b",
    rf"\b(papers?|publications?|research|work)\b.*\b{_AUTHOR_VERBS}\b",
    rf"\b{_AUTHOR_VERBS}\b.*\b(papers?|publications?)\b",
    rf"\bwhat\s+(did|has)\b.*\b{_AUTHOR_VERBS}\b",
    r"\blist\b.*\b(papers?|publications?)\b.*\b(by|of|from)\b",
    r"\b(papers?|publications?)\s+(by|of|from)\b",
]

# Query tokens that must never be treated as a person's name when doing
# partial-name matching (common question words + typo variants).
_QUERY_STOPWORDS = {
    "what", "which", "papers", "paper", "publications", "publication",
    "research", "resarch", "rsearch", "rsrch", "work", "works", "wrote",
    "write", "written", "writes", "authored", "author", "authors",
    "published", "publish", "list", "show", "give", "tell", "did", "has",
    "have", "the", "this", "that", "many", "how", "about", "does", "doctor",
    "professor", "lecturer", "engineer", "from", "campus", "university",
    "bahria",
}


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
    # (full_name, researcher_id) for every researcher the answer concerns —
    # one entry normally, several when asking the user to disambiguate.
    researchers: list[tuple[str, int]]


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


def _resolve_researchers(message: str) -> list[dict]:
    """Find researcher(s) named in the question.

    Two stages:
    1. Full-name containment (normalized, title-stripped) — an unambiguous
       match like 'Arif Ur Rahman'; the longest wins and is returned alone.
    2. Partial-name tokens — a bare 'arif' matches every researcher with that
       name token, so ALL matches are returned and the caller asks the user
       which one they meant instead of guessing.
    """
    q_norm = _norm_name(message)
    researchers = _Store.researchers()

    # Stage 1: full-name match (longest wins — 'Arif Ur Rahman' over 'Rahman').
    best: dict | None = None
    best_len = 0
    for r in researchers:
        raw = re.sub(rf"^{_TITLES}", "", r["full_name"].strip(), flags=re.I)
        name_norm = _norm_name(raw)
        if len(name_norm) >= 6 and name_norm in q_norm and len(name_norm) > best_len:
            best, best_len = r, len(name_norm)
    if best is not None:
        return [best]

    # Stage 2: partial-name tokens from the question (skip question words).
    q_tokens = {
        _NAME_VARIANTS.get(t, t)
        for t in re.findall(r"[a-z]+", message.lower())
        if len(t) >= 3 and t not in _QUERY_STOPWORDS
    }
    if not q_tokens:
        return []
    matches = []
    for r in researchers:
        raw = re.sub(rf"^{_TITLES}", "", r["full_name"].strip(), flags=re.I)
        name_tokens = {
            _NAME_VARIANTS.get(t, t)
            for t in re.findall(r"[a-z]+", raw.lower()) if len(t) >= 3
        }
        if q_tokens & name_tokens:
            matches.append(r)
    return matches


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


_DISAMBIGUATION_MARKER = "Which one do you mean?"


def answer(message: str, history: list | None = None) -> AuthoredResult | None:
    """Return a structured authored-papers answer, or None to fall through.

    One matched researcher -> their publication list (from the structured
    table). Several matches (e.g. a bare 'arif' when two researchers carry
    that name) -> ask the user which one they meant rather than guessing.
    A reply naming one of the candidates right after that question is treated
    as the answer to it, even without authorship words.
    """
    replying_to_disambiguation = bool(
        history
        and getattr(history[-1], "role", "") == "assistant"
        and _DISAMBIGUATION_MARKER in getattr(history[-1], "content", "")
    )
    if not is_authored_query(message) and not replying_to_disambiguation:
        return None
    matches = _resolve_researchers(message)
    if not matches:
        return None

    if len(matches) > 1:
        # Ambiguous partial name: never guess — ask.
        shown = matches[:5]
        lines = [f"I found {len(matches)} researchers matching that name. "
                 f"{_DISAMBIGUATION_MARKER}"]
        for r in shown:
            lines.append(f"- {r['full_name']} ({r['designation']}, "
                         f"{r['campus']} campus)")
        if len(matches) > len(shown):
            lines.append(f"...and {len(matches) - len(shown)} more.")
        return AuthoredResult(
            answer="\n".join(lines),
            researchers=[(r["full_name"], r["researcher_id"]) for r in shown],
        )

    researcher = matches[0]
    rid = researcher["researcher_id"]
    name = researcher["full_name"]
    pubs = _publications_for(rid)

    if not pubs:
        return AuthoredResult(
            answer=(f"I don't have any publications on record for {name} in the "
                    f"ResearchSense database."),
            researchers=[(name, rid)],
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
        researchers=[(name, rid)],
    )
