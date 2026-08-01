"""Pure enrichment helpers for fetch_publications: field-guard attribution,
international-collaboration flags, hybrid research-area derivation, and
supplementary-source merging.

Split out of fetch_publications.py to keep that module under the repo's
line-count guideline; re-exported there for backward-compatible imports.
"""

from __future__ import annotations

import re
from collections import Counter

from scripts.fetch_sources import dedupe_key


def expertise_field_guard(work_topic_names: list[str], expertise_text: str) -> bool:
    """Attribution guard for ALL departments: the work's topic words must
    overlap the researcher's expertise/department words. Empty expertise
    rejects (an anchored internal co-authorship may still link, as before)."""
    if not (expertise_text or "").strip():
        return False
    exp = set(re.findall(r"[a-z]{4,}", expertise_text.lower()))
    work = {
        t
        for name in work_topic_names
        for t in re.findall(r"[a-z]{4,}", (name or "").lower())
    }
    return bool(exp & work)


def international_of(institutions: list[dict]) -> bool:
    return any((i.get("country") or "") not in ("", "PK") for i in institutions)


def derive_research_areas(
    researcher: dict, linked_pubs: list[dict], top_n: int = 5
) -> list[str]:
    """Hybrid areas: most frequent topic names across the researcher's actual
    publications; fallback to their cleaned directory expertise."""
    counts: Counter = Counter()
    for p in linked_pubs:
        for name in p.get("topic_names") or []:
            counts[name] += 1
    ranked = [name for name, _ in counts.most_common(top_n)]
    if ranked:
        return ranked
    return (researcher.get("expertise_areas") or [])[:top_n]


def _dedupe_keys(p: dict) -> set[str]:
    """Both the doi-based key (if a doi exists) and the title-based key, so a
    doi-bearing record still guards against a doi-less duplicate matched only
    by title (dedupe_key alone picks one or the other, never both)."""
    title = p.get("title", "")
    year = p.get("publication_year", 0)
    keys = {dedupe_key(None, title, year)}
    doi = p.get("doi")
    if doi:
        keys.add(dedupe_key(doi, title, year))
    return keys


def backfill_topic_names(publications: list[dict]) -> None:
    """Publications that carry a legacy `topics` list but no `topic_names`
    (faculty-submitted records re-merged from submitted_publications.json,
    which never set topic_names) get topic_names filled in from `topics` so
    they still count toward research-area derivation and keep an id through
    the dynamic topics.json rewrite instead of being silently wiped."""
    for p in publications:
        if not p.get("topic_names") and p.get("topics"):
            p["topic_names"] = [t["topic_name"] for t in p["topics"]]


def merge_supplementary(primary: list[dict], extra: list[dict]) -> list[dict]:
    seen: set[str] = set()
    for p in primary:
        seen |= _dedupe_keys(p)
    out = list(primary)
    for p in extra:
        keys = _dedupe_keys(p)
        if keys & seen:
            continue
        seen |= keys
        out.append(p)
    return out
