"""Writes into an institution's own workspace.

Only ever called for a signed-in workspace account, and only with data the
researcher has reviewed and accepted. The bundled demo corpus is never written
to from here.
"""

from __future__ import annotations

from app.repositories import loader


def _rows(name: str, workspace: str) -> list[dict]:
    """Read a workspace file directly (not through the request-scoped cache)."""
    return loader._load(name, workspace)  # noqa: SLF001 - same package boundary


def _topic_table(areas: list[str]) -> list[dict]:
    return [
        {
            "topic_id": i + 1,
            "topic_name": area,
            "description": "",
            "icon": "sparkles",
            "publication_count": 0,
            "researcher_count": 1,
            "source": "self-service",
        }
        for i, area in enumerate(areas)
    ]


def _publication_record(
    pub_id: int, item: dict, author: dict, campus: str, topic_refs: list[dict]
) -> dict:
    year = item.get("publication_year")
    return {
        "publication_id": pub_id,
        "title": (item.get("title") or "").strip(),
        "abstract": "",
        "doi": (item.get("doi") or None),
        "publication_year": int(year) if year else 0,
        "publication_date": None,
        "journal_name": (item.get("journal_name") or "").strip(),
        "publication_type": item.get("publication_type") or "journal",
        "citation_count": int(item.get("citation_count") or 0),
        "campus": campus,
        "authors": [
            {
                "researcher_id": author["researcher_id"],
                "full_name": author["full_name"],
                "order": 1,
            }
        ],
        "topics": topic_refs,
        "topic_names": [t["topic_name"] for t in topic_refs],
        "coauthor_institutions": [],
        "international": False,
        "source": item.get("source") or "self-service",
    }


def apply_profile(workspace: str, researcher_id: int, profile: dict) -> dict:
    """Update the owner's profile from the accepted review form."""
    researchers = list(_rows("researchers", workspace))
    if not researchers:
        raise ValueError("workspace has no researcher profile")

    areas = [a for a in (profile.get("research_areas") or []) if a]
    topics = _topic_table(areas)
    topic_refs = [
        {"topic_id": t["topic_id"], "topic_name": t["topic_name"]} for t in topics
    ]

    for r in researchers:
        if r.get("researcher_id") != researcher_id:
            continue
        r.update(
            {
                "full_name": profile.get("full_name") or r.get("full_name", ""),
                "designation": profile.get("designation") or r.get("designation", ""),
                "academic_rank": profile.get("designation")
                or r.get("academic_rank", ""),
                "department": profile.get("department") or r.get("department", ""),
                "education": profile.get("education") or "",
                "profile_bio": profile.get("profile_bio") or "",
                "expertise": ", ".join(areas),
                "research_areas": areas,
                "topics": topic_refs,
            }
        )
        break

    loader.save("researchers", researchers, workspace)
    loader.save("topics", topics, workspace)
    return {"research_areas": areas}


def add_publications(workspace: str, researcher_id: int, items: list[dict]) -> int:
    """Append accepted publications, skipping ones already recorded.

    Returns how many were added. Also refreshes the owner's publication and
    citation counts and the per-topic publication counts, so the profile and
    analytics agree with the list.
    """
    researchers = list(_rows("researchers", workspace))
    author = next(
        (r for r in researchers if r.get("researcher_id") == researcher_id), None
    )
    if author is None:
        raise ValueError("workspace has no researcher profile")

    existing = list(_rows("publications", workspace))
    seen_titles = {(p.get("title") or "").strip().lower() for p in existing}
    seen_dois = {(p.get("doi") or "").lower() for p in existing if p.get("doi")}
    next_id = max((p.get("publication_id", 0) for p in existing), default=0) + 1

    topics = list(_rows("topics", workspace))
    topic_refs = [
        {"topic_id": t["topic_id"], "topic_name": t["topic_name"]} for t in topics
    ]
    campus = author.get("campus") or ""

    added = 0
    for item in items:
        title = (item.get("title") or "").strip()
        doi = (item.get("doi") or "").strip().lower()
        if not title:
            continue
        if title.lower() in seen_titles or (doi and doi in seen_dois):
            continue
        existing.append(_publication_record(next_id, item, author, campus, topic_refs))
        seen_titles.add(title.lower())
        if doi:
            seen_dois.add(doi)
        next_id += 1
        added += 1

    if added:
        loader.save("publications", existing, workspace)

    # Keep the profile counters and topic counts in step with the list.
    author["publication_count"] = len(existing)
    author["citation_count"] = sum(int(p.get("citation_count") or 0) for p in existing)
    loader.save("researchers", researchers, workspace)

    if topics:
        for t in topics:
            t["publication_count"] = len(existing)
        loader.save("topics", topics, workspace)

    return added
