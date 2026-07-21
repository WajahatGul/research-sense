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


# ---------------------------------------------------------------------------
# Co-authorship fast path ("what did X and Y write together / collaborate")
# ---------------------------------------------------------------------------

# Name particles never treated as identifying (surname detection skips them).
_PARTICLES = {"ur", "ul", "al", "bin", "binti", "ibn", "abu", "el", "de"}

_COLLAB_PATTERNS = [
    r"\b(collaborat\w*|co-?author\w*|jointly|co-?wrote|co-?written)\b",
    r"\btogether\b",
    r"\b(wrote|written|write|writes|worked|work|working|published|publish|"
    r"paper|papers|research)\b[^.?!]*\bwith\b",
    r"\bbetween\b[^.?!]*\band\b",
]


def is_collaboration_query(message: str) -> bool:
    """True if the message asks about two people collaborating / co-authoring."""
    lower = message.lower()
    return any(re.search(p, lower) for p in _COLLAB_PATTERNS)


def _sig_tokens(name: str) -> list[str]:
    raw = re.sub(rf"^{_TITLES}", "", name.strip(), flags=re.I)
    return [
        _NAME_VARIANTS.get(t, t)
        for t in re.findall(r"[a-z]+", raw.lower())
        if len(t) >= 3 and t not in _PARTICLES
    ]


def _full_name_matches(message: str) -> list[dict]:
    """Researchers whose full name appears contiguously in the query — the
    most reliable signal ('Arif Ur Rahman' won't match 'Wajiha Arif')."""
    q_norm = _norm_name(message)
    out = []
    for r in _Store.researchers():
        raw = re.sub(rf"^{_TITLES}", "", r["full_name"].strip(), flags=re.I)
        name_norm = _norm_name(raw)
        if len(name_norm) >= 8 and name_norm in q_norm:
            out.append(r)
    # Longest names first, so the fullest match leads.
    out.sort(key=lambda r: len(_norm_name(r["full_name"])), reverse=True)
    return out


def _resolve_people(message: str) -> list[dict]:
    """Ordered, distinct researchers named in the message: contiguous
    full-name matches first, then researchers matching two or more name tokens
    (a lone shared first name is not enough to add a second person)."""
    q_tokens = {
        _NAME_VARIANTS.get(t, t)
        for t in re.findall(r"[a-z]+", message.lower())
        if len(t) >= 3 and t not in _QUERY_STOPWORDS
    }
    people = _full_name_matches(message)
    seen = {r["researcher_id"] for r in people}
    strong: list[tuple] = []
    for r in _Store.researchers():
        if r["researcher_id"] in seen:
            continue
        sig = _sig_tokens(r["full_name"])
        matched = [t for t in sig if t in q_tokens]
        if len(matched) >= 2:  # two tokens — not a single first-name collision
            strong.append((len(matched), r))
    strong.sort(key=lambda x: x[0], reverse=True)
    people.extend(r for _s, r in strong)
    return people


def _coauthors_of(researcher_id: int) -> list[tuple[str, int]]:
    from collections import Counter

    names = {r["researcher_id"]: r["full_name"] for r in _Store.researchers()}
    counter: Counter = Counter()
    for p in _Store.pubs():
        ids = {a["researcher_id"] for a in p.get("authors", [])
               if a.get("researcher_id") in names}
        if researcher_id in ids:
            for other in ids:
                if other != researcher_id:
                    counter[other] += 1
    return [(names[o], c) for o, c in counter.most_common()]


def _shared_publications(a_id: int, b_id: int) -> list[dict]:
    out = []
    for p in _Store.pubs():
        ids = {au.get("researcher_id") for au in p.get("authors", [])}
        if a_id in ids and b_id in ids:
            out.append(p)
    out.sort(key=lambda p: p.get("publication_year") or 0, reverse=True)
    return out


def collaboration_answer(message: str) -> AuthoredResult | None:
    """Answer collaboration questions from structured data.

    - Two people ("did X and Y write together") -> their shared publications,
      or an honest "not co-authored" with any shared research areas.
    - One person ("who has X collaborated with") -> that person's co-authors.

    Falls through (None) unless it is a collaboration question naming someone.
    """
    if not is_collaboration_query(message):
        return None
    people = _resolve_people(message)
    if not people:
        return None

    if len(people) == 1:
        r = people[0]
        coauthors = _coauthors_of(r["researcher_id"])
        if coauthors:
            listing = "\n".join(
                f"- {n} ({c} paper{'s' if c > 1 else ''})" for n, c in coauthors)
            answer = (f"{r['full_name']} has co-authored papers with:\n{listing}")
        else:
            answer = (f"{r['full_name']} has no co-authored papers with other "
                      f"researchers in the database.")
        return AuthoredResult(
            answer=answer,
            researchers=[(r["full_name"], r["researcher_id"])],
        )

    a, b = people[0], people[1]
    shared = _shared_publications(a["researcher_id"], b["researcher_id"])
    if shared:
        lines = [f"{a['full_name']} and {b['full_name']} have co-authored "
                 f"{len(shared)} paper(s):"]
        for p in shared[:12]:
            year = p.get("publication_year") or "n.d."
            venue = p.get("journal_name") or ""
            tail = (f" - {venue}"
                    if venue and venue != "Preprint or unindexed venue" else "")
            lines.append(f"- {p['title']} ({year}){tail}")
        answer = "\n".join(lines)
    else:
        a_areas = {t["topic_name"] for t in a.get("topics", [])}
        b_areas = {t["topic_name"] for t in b.get("topics", [])}
        common = sorted(a_areas & b_areas)
        answer = (f"{a['full_name']} and {b['full_name']} have not co-authored "
                  f"any papers in the ResearchSense database.")
        if common:
            answer += (f" They do share research interests in "
                       f"{', '.join(common)}, so they could be potential "
                       f"collaborators.")
        else:
            answer += " They also have no overlapping research areas on record."
    return AuthoredResult(
        answer=answer,
        researchers=[(a["full_name"], a["researcher_id"]),
                     (b["full_name"], b["researcher_id"])],
    )
