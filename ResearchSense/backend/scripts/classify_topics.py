"""File each research area under a broad field, so 769 areas can be browsed.

The areas are OpenAlex topics, and OpenAlex already places every topic in a
hierarchy (topic -> subfield -> field -> domain): "Topic Modeling" sits under
Computer Science, "Islamic Finance and Banking Studies" under Economics,
Econometrics and Finance. That hierarchy is downloaded once and cached in
``openalex_topics.json``; each area is matched to it by exact name.

About a third of the areas come from people's own directory expertise
("Tafseer", "Tax Law", "CPEC") rather than from OpenAlex. Those are placed
by the people who list them: each department's field is the one most of its
OpenAlex-matched areas fall under, and the area goes where most of its
people's departments point. Such placements are marked
``field_source: "department"``. An area neither step can place gets no
field and is shown under "Other".

    python -m scripts.classify_topics          # dry run: counts per field
    python -m scripts.classify_topics --write  # write field/domain to topics.json
"""

from __future__ import annotations

import json
import sys
import time
from collections import Counter
from pathlib import Path

import httpx

DATA_DIR = Path(__file__).parent.parent / "app" / "data"
API = "https://api.openalex.org"
HEADERS = {"User-Agent": "ResearchSense/0.1 (mailto:dev@stocklenshq.com)"}
CACHE = DATA_DIR / "openalex_topics.json"


def _get(client: httpx.Client, path: str, params: dict) -> dict:
    for attempt in range(4):
        r = client.get(f"{API}{path}", params=params, headers=HEADERS, timeout=30)
        if r.status_code == 200:
            return r.json()
        time.sleep(1.5 * (attempt + 1))
    r.raise_for_status()
    return {}


def _slim(t: dict) -> dict:
    return {
        "name": t["display_name"],
        "subfield": (t.get("subfield") or {}).get("display_name", ""),
        "field": (t.get("field") or {}).get("display_name", ""),
        "domain": (t.get("domain") or {}).get("display_name", ""),
    }


def hierarchy(client: httpx.Client) -> list[dict]:
    """Every OpenAlex topic with its field and domain (cached on disk)."""
    if CACHE.exists():
        return json.loads(CACHE.read_text("utf-8"))
    rows, cursor = [], "*"
    while cursor:
        page = _get(client, "/topics", {
            "per-page": 200, "cursor": cursor,
            "select": "display_name,subfield,field,domain",
        })
        rows += [_slim(t) for t in page.get("results", [])]
        cursor = page.get("meta", {}).get("next_cursor")
    CACHE.write_text(json.dumps(rows, ensure_ascii=False, indent=1), "utf-8")
    return rows


def _key(name: str) -> str:
    return " ".join(name.lower().replace("’", "'").split())


def classify(
    topics: list[dict], researchers: list[dict], client: httpx.Client | None = None
) -> list[dict]:
    """Set field/domain on each topic in place; return those placed by department."""
    known = {_key(t["name"]): t for t in hierarchy(client or httpx.Client())}
    matched = {t["topic_name"]: known.get(_key(t["topic_name"])) for t in topics}

    directory = [r for r in researchers if r.get("source") != "openalex"]
    dept_fields: dict[str, Counter] = {}
    for r in directory:
        c = dept_fields.setdefault(r.get("department") or "", Counter())
        for name in r.get("research_areas") or []:
            if matched.get(name):
                c[(matched[name]["field"], matched[name]["domain"])] += 1
    dept_field = {d: c.most_common(1)[0][0] for d, c in dept_fields.items() if c}

    by_department = []
    for t in topics:
        for k in ("field", "domain", "field_source"):
            t.pop(k, None)
        hit = matched[t["topic_name"]]
        if hit and hit["field"]:
            t["field"], t["domain"], t["field_source"] = hit["field"], hit["domain"], "openalex"
            continue
        votes = Counter(
            dept_field[r["department"]]
            for r in directory
            if t["topic_name"] in (r.get("research_areas") or [])
            and r.get("department") in dept_field
        )
        if votes:
            (t["field"], t["domain"]), _ = votes.most_common(1)[0]
            t["field_source"] = "department"
            by_department.append(t)
    return by_department


def main(write: bool) -> None:
    path = DATA_DIR / "topics.json"
    topics = json.loads(path.read_text("utf-8"))
    researchers = json.loads((DATA_DIR / "researchers.json").read_text("utf-8"))
    with httpx.Client() as client:
        placed = classify(topics, researchers, client)
    per_field = Counter(t.get("field", "Other") for t in topics)
    for field, n in per_field.most_common():
        print(f"  {n:>4}  {field}")
    print(f"{len(topics)} areas, {len(placed)} placed by department")
    for t in placed[:60]:
        print(f"    {t['topic_name']!r} -> {t['field']}")
    if write:
        path.write_text(json.dumps(topics, ensure_ascii=False, indent=2), "utf-8")


if __name__ == "__main__":
    main("--write" in sys.argv)
