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
