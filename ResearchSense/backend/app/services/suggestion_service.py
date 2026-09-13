"""Starter questions for the assistant, built from the workspace's own data.

The chips shown in an empty chat used to be fixed strings naming Bahria
researchers and campuses. An institution that signed up saw them too, so its
very first click was guaranteed to return "I could not find anything" — the
worst possible introduction to the product.

These are derived from whatever the current workspace actually holds, so they
always lead somewhere. An empty workspace gets none, and the UI falls back to
inviting the researcher to add their own work.
"""

from __future__ import annotations

from app.repositories import loader

# Enough to fill the chip row without pushing the input box off screen.
MAX_SUGGESTIONS = 3


def _most_published(researchers: list[dict]) -> dict | None:
    ranked = [r for r in researchers if (r.get("full_name") or "").strip()]
    if not ranked:
        return None
    return max(ranked, key=lambda r: r.get("publication_count") or 0)


def _busiest_area(researchers: list[dict], topics: list[dict]) -> str | None:
    """The area the most people work on — the one worth asking about."""
    counts: dict[str, int] = {}
    for r in researchers:
        areas = r.get("research_areas") or [
            t.get("topic_name") for t in (r.get("topics") or [])
        ]
        for area in areas:
            if area:
                counts[area] = counts.get(area, 0) + 1
    if counts:
        return max(counts, key=lambda a: counts[a])
    named = [t.get("topic_name") for t in topics if t.get("topic_name")]
    return named[0] if named else None


def _recent_paper(publications: list[dict]) -> dict | None:
    titled = [p for p in publications if (p.get("title") or "").strip()]
    if not titled:
        return None
    return max(titled, key=lambda p: p.get("publication_year") or 0)


def suggestions() -> list[str]:
    """Up to three questions this workspace can genuinely answer."""
    researchers = loader.load("researchers")
    publications = loader.load("publications")
    topics = loader.load("topics")

    out: list[str] = []

    area = _busiest_area(researchers, topics)
    if area:
        # Name a campus only when there is more than one to choose between,
        # so a single-campus institution is not asked a pointless question.
        campuses = {
            (r.get("campus") or "").strip() for r in researchers if r.get("campus")
        }
        if len(campuses) > 1:
            busiest_campus = max(
                campuses,
                key=lambda c: sum(1 for r in researchers if r.get("campus") == c),
            )
            out.append(f"Who works on {area} in {busiest_campus}?")
        else:
            out.append(f"Who works on {area}?")

    author = _most_published(researchers)
    if author and (author.get("publication_count") or 0) > 0:
        out.append(f"What papers has {author['full_name']} written?")

    paper = _recent_paper(publications)
    if paper and len(out) < MAX_SUGGESTIONS:
        title = paper["title"].strip()
        if len(title) > 60:
            title = title[:60].rstrip() + "…"
        out.append(f'What is the paper "{title}" about?')

    if researchers and len(out) < MAX_SUGGESTIONS:
        out.append("Who has the most publications?")

    return out[:MAX_SUGGESTIONS]
