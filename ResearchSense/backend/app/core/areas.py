"""Who works on a research area: one rule for every screen that asks.

A person's areas are derived from their papers (the five most frequent
topics) and are usually specific: Shehzad Khalid's read "Radiomics and
Machine Learning in Medical Imaging", "EEG and Brain-Computer Interfaces".
Their own directory entry says, in their words, "Machine Learning". Counting
only the derived areas left the most published machine-learning researcher
off the Machine Learning page, out of its head count and out of the
assistant's answer, while the search box (which reads expertise) found him:
the same question answered three ways. An area now includes anyone who has
it among their derived areas OR lists it as their expertise.
"""

from __future__ import annotations

import re
from collections import Counter


def _norm(name: str) -> str:
    return " ".join((name or "").lower().split())


def areas_of(researcher: dict) -> set[str]:
    """Every area this person works on, normalised for comparison."""
    names = set(researcher.get("research_areas") or [])
    names.update(researcher.get("expertise_areas") or [])
    names.update(
        t.get("topic_name", "")
        for t in researcher.get("topics") or []
        if isinstance(t, dict)
    )
    return {_norm(n) for n in names if n and n.strip()}


def works_in(researcher: dict, area: str) -> bool:
    return _norm(area) in areas_of(researcher)


# --- which papers belong to an area ------------------------------------------
#
# A paper counted towards an area only when it was tagged with exactly that
# label, and only its first four labels were looked at. OpenAlex tags papers
# with narrow topics ("Radiomics and Machine Learning in Medical Imaging"), so
# the Machine Learning area listed 4 papers beside 24 researchers, and
# Islamic Finance and Banking Studies showed 59 of the 231 papers tagged with
# it. A paper now belongs to an area when any of its topics is the area or a
# narrower topic whose name contains the area's whole name. Only names of two
# words or more are matched inside others, so "Health" does not swallow every
# paper that mentions health.

_WORD = re.compile(r"[a-z0-9]+")
_paper_index: dict[tuple[int, int], tuple[dict[int, set[int]], Counter]] = {}


def _words(name: str) -> tuple[str, ...]:
    return tuple(_WORD.findall((name or "").lower()))


def paper_areas(topics: list[dict], publications: list[dict]) -> tuple[dict[int, set[int]], Counter]:
    """(paper id -> area ids, area id -> paper count) for this dataset, cached."""
    key = (id(topics), id(publications))
    if key not in _paper_index:
        exact = {_words(t["topic_name"]): t["topic_id"] for t in topics}
        phrases: dict[tuple[str, ...], list[int]] = {}
        for t in topics:
            w = _words(t["topic_name"])
            if len(w) >= 2:
                phrases.setdefault(w, []).append(t["topic_id"])
        of_paper: dict[int, set[int]] = {}
        counts: Counter = Counter()
        for p in publications:
            ids = {t["topic_id"] for t in p.get("topics", [])}
            for name in p.get("topic_names") or []:
                w = _words(name)
                if w in exact:
                    ids.add(exact[w])
                for n in range(2, len(w) + 1):
                    for i in range(len(w) - n + 1):
                        ids.update(phrases.get(w[i:i + n], ()))
            of_paper[p["publication_id"]] = ids
            counts.update(ids)
        _paper_index.clear()
        _paper_index[key] = (of_paper, counts)
    return _paper_index[key]
