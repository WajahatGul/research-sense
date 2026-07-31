"""Shared normalization for names, departments, and expertise strings.

Used by the pipeline scripts (scrape, seed, fetch) so every honorific strip
and department/area spelling decision lives in exactly one place (SRS 3, 2).
"""

from __future__ import annotations

import re

_TITLES = (
    r"(?:dr|prof(?:essor)?|engineer|engr|mr|mrs|ms|miss|madam|capt|col|maj|brig|lt)"
)
_TITLE_RE = re.compile(rf"^(?:{_TITLES})(?:\.\s*|\s+)", re.I)

# Department acronyms to always uppercase (both for recovery of mangled
# input and future all-caps preservation).
_DEPT_ACRONYMS = {"hr", "ipp"}

# Compound-variant map applied to individual expertise phrases (lowercased).
_AREA_VARIANTS = {
    "ai": "Artificial Intelligence",
    "artificial intelligence": "Artificial Intelligence",
    "ml": "Machine Learning",
    "machine learning": "Machine Learning",
    "dl": "Deep Learning",
    "nlp": "Natural Language Processing",
    "natural language processing": "Natural Language Processing",
    "iot": "Internet of Things",
    "internet of things": "Internet of Things",
    "hci": "Human Computer Interaction",
    "cv": "Computer Vision",
    "cyber security": "Cybersecurity",
    "information security": "Cybersecurity",
    "data sciences": "Data Science",
    "data analytics": "Data Science",
}


def normalize_name(raw: str) -> str:
    """Strip leading honorifics (stacked too) and collapse whitespace."""
    name = re.sub(r"\s+", " ", (raw or "").strip())
    while _TITLE_RE.match(name):
        name = _TITLE_RE.sub("", name, count=1)
    return name.strip()


def canonical_department(raw: str) -> str:
    """One display form per department: no 'Department of', '&'->'and',
    title case, whitespace collapsed. Empty input maps to 'General'.
    Preserves fully-uppercase words (len >= 2)."""
    s = re.sub(r"\s+", " ", (raw or "").strip())
    # Track which words in the normalized string are fully uppercase
    all_caps_words = {w.lower() for w in s.split(" ") if w.isupper() and len(w) >= 2}
    s = re.sub(r"^department\s+of\s+", "", s, flags=re.I)
    s = s.replace("&", "and")
    if not s:
        return "General"
    small = {"of", "and", "in", "for", "the"}
    words = []
    for i, w in enumerate(s.split(" ")):
        w_lower = w.lower()
        if w_lower in all_caps_words or w_lower in _DEPT_ACRONYMS:
            words.append(w_lower.upper())
        elif w_lower in small and i > 0:
            words.append(w)
        else:
            words.append(w.capitalize())
    return " ".join(words)


def split_expertise(raw: str) -> list[str]:
    """Split a free-text expertise string into clean area phrases.

    Splits on , ; / and the word 'and'; canonicalizes known variants;
    dedupes case-insensitively, preserving first-seen order.
    """
    if not (raw or "").strip():
        return []
    parts = re.split(r"[,;/]|\band\b", raw, flags=re.I)
    seen: dict[str, str] = {}
    for p in parts:
        p = re.sub(r"\s+", " ", p).strip(" .")
        if len(p) < 2:
            continue
        canon = _AREA_VARIANTS.get(p.lower())
        if canon is None:
            canon = " ".join(w if w.isupper() else w.capitalize() for w in p.split(" "))
        seen.setdefault(canon.lower(), canon)
    return list(seen.values())
