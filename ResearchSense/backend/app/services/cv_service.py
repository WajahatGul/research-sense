"""Read a pasted CV into a draft profile and publication list.

The extraction is deliberately generous: it pulls out everything the CV
contains. Nothing here is authoritative — the caller shows the result in an
editable review form and only writes it to the workspace once the researcher
has corrected and accepted it (see docs/design/multi-tenant-onboarding.md).
"""

from __future__ import annotations

import json
import re

from app.services.rag import agentic

_MAX_CV_CHARS = 24000

_SYSTEM = (
    "You extract structured facts from an academic CV. Return ONLY a JSON "
    "object, no prose and no markdown fences.\n\n"
    "Schema:\n"
    "{\n"
    '  "full_name": string,\n'
    '  "designation": string,        // e.g. Assistant Professor\n'
    '  "department": string,\n'
    '  "institution": string,\n'
    '  "education": string,          // one line, highest degree first\n'
    '  "research_areas": [string],   // 3 to 8 short areas\n'
    '  "profile_bio": string,        // 2 to 3 sentences, factual\n'
    '  "publications": [\n'
    '    {"title": string, "publication_year": number|null,\n'
    '     "journal_name": string, "doi": string|null}\n'
    "  ]\n"
    "}\n\n"
    "Rules: copy values verbatim from the CV; never invent a title, year, "
    "venue, or DOI. Use null when a value is absent. Include every publication "
    "you can find. If the CV is unusable, return the schema with empty values."
)


def available() -> bool:
    """CV reading needs the language model; without it we fall back to a
    blank form the researcher fills in by hand."""
    return agentic.available()


def _coerce_publications(raw: object) -> list[dict]:
    out: list[dict] = []
    if not isinstance(raw, list):
        return out
    for item in raw:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or "").strip()
        if not title:
            continue
        year = item.get("publication_year")
        try:
            year = int(year) if year is not None else None
        except (TypeError, ValueError):
            year = None
        if year is not None and not (1900 <= year <= 2100):
            year = None
        doi = item.get("doi")
        doi = str(doi).strip() if doi else None
        out.append(
            {
                "title": title[:300],
                "publication_year": year,
                "journal_name": str(item.get("journal_name") or "").strip()[:300],
                "doi": doi,
            }
        )
    return out


def _blank() -> dict:
    return {
        "full_name": "",
        "designation": "",
        "department": "",
        "institution": "",
        "education": "",
        "profile_bio": "",
        "research_areas": [],
        "publications": [],
    }


def parse_cv(text: str) -> dict:
    """Return a draft profile + publications read from CV text.

    Always returns the full shape so the review form can render, even when the
    model is unavailable or the CV yields nothing.
    """
    draft = _blank()
    cv = (text or "").strip()
    if not cv or not available():
        return draft

    raw = agentic._groq_call(
        [
            {"role": "system", "content": _SYSTEM},
            {"role": "user", "content": cv[:_MAX_CV_CHARS]},
        ],
        temperature=0.0,
        max_tokens=4000,
        label="cv-extract",
    )
    if not raw:
        return draft

    # The model is told to return bare JSON; strip a stray fence just in case.
    cleaned = re.sub(r"^\s*```[a-zA-Z]*|```\s*$", "", raw.strip())
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", cleaned, re.S)
        if not match:
            return draft
        try:
            data = json.loads(match.group(0))
        except json.JSONDecodeError:
            return draft
    if not isinstance(data, dict):
        return draft

    areas = data.get("research_areas")
    draft.update(
        {
            "full_name": str(data.get("full_name") or "").strip()[:200],
            "designation": str(data.get("designation") or "").strip()[:120],
            "department": str(data.get("department") or "").strip()[:120],
            "institution": str(data.get("institution") or "").strip()[:200],
            "education": str(data.get("education") or "").strip()[:500],
            "profile_bio": str(data.get("profile_bio") or "").strip()[:1200],
            "research_areas": [
                str(a).strip()[:80]
                for a in (areas if isinstance(areas, list) else [])
                if str(a).strip()
            ][:10],
            "publications": _coerce_publications(data.get("publications")),
        }
    )
    return draft
