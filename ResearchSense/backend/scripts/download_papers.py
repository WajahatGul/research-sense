"""Download open-access papers of a faculty member from OpenAlex.

MVP corpus for the RAG chatbot: up to 20 real open-access PDFs authored by
Dr. Arif ur Rahman (Bahria University). OpenAlex lists an open-access PDF URL
for many works (``best_oa_location.pdf_url``); we download those into
``backend/papers/`` and record a manifest so the indexer can attach real
title/year/DOI metadata to every text chunk.

Run (from backend/):
    python -m scripts.download_papers
"""
from __future__ import annotations

import json
import re
import time
from pathlib import Path
from urllib.parse import urljoin

import httpx

API = "https://api.openalex.org"
HEADERS = {"User-Agent": "Mozilla/5.0 ResearchSense/0.1 (mailto:dev@stocklenshq.com)"}
INSTITUTION = "I59225215"  # Bahria University
AUTHOR_NAME = "Arif ur Rahman"
MAX_PAPERS = 20

PAPERS_DIR = Path(__file__).resolve().parent.parent / "papers"
MANIFEST = PAPERS_DIR / "manifest.json"


def find_author_id() -> str:
    r = httpx.get(f"{API}/authors", params={
        "search": AUTHOR_NAME,
        "filter": f"affiliations.institution.id:{INSTITUTION}",
        "per_page": 5,
    }, headers=HEADERS, timeout=40)
    r.raise_for_status()
    results = r.json()["results"]
    if not results:
        raise SystemExit(f"No OpenAlex author found for {AUTHOR_NAME} at Bahria.")
    # Highest works count among Bahria-affiliated matches is our researcher.
    best = max(results, key=lambda a: a["works_count"])
    print(f"  author: {best['display_name']} ({best['id']}) "
          f"works={best['works_count']} cited={best['cited_by_count']}")
    return best["id"].split("/")[-1]


def _pdf_candidates(work: dict) -> list[str]:
    """Every PDF URL OpenAlex knows for a work, best first, de-duplicated."""
    urls: list[str] = []
    for loc in ([work.get("best_oa_location"), work.get("primary_location")]
                + (work.get("locations") or [])):
        pdf = (loc or {}).get("pdf_url")
        if pdf and pdf not in urls:
            urls.append(pdf)
    return urls


def _landing_pages(work: dict) -> list[str]:
    pages: list[str] = []
    for loc in ([work.get("best_oa_location"), work.get("primary_location")]
                + (work.get("locations") or [])):
        url = (loc or {}).get("landing_page_url")
        if url and url not in pages:
            pages.append(url)
    return pages


def _pdf_from_landing_page(client: httpx.Client, page_url: str) -> str | None:
    """Scan a landing page for a direct .pdf link (repositories, Springer)."""
    try:
        resp = client.get(page_url)
        if resp.status_code != 200:
            return None
        links = re.findall(r"href=[\"']([^\"']*\.pdf[^\"']*)", resp.text, re.I)
        return urljoin(str(resp.url), links[0]) if links else None
    except httpx.HTTPError:
        return None


def _semantic_scholar_pdf(doi: str | None, client: httpx.Client) -> str | None:
    """Free second source: Semantic Scholar's open-access PDF link, if any."""
    if not doi:
        return None
    try:
        r = client.get(
            f"https://api.semanticscholar.org/graph/v1/paper/DOI:{doi}",
            params={"fields": "openAccessPdf"}, timeout=30)
        if r.status_code == 200:
            return (r.json().get("openAccessPdf") or {}).get("url")
    except httpx.HTTPError:
        pass
    return None


def list_works(author_id: str) -> list[dict]:
    r = httpx.get(f"{API}/works", params={
        "filter": f"author.id:{author_id}",
        "per_page": 100,
        "sort": "cited_by_count:desc",
    }, headers=HEADERS, timeout=60)
    r.raise_for_status()
    works = []
    for w in r.json()["results"]:
        works.append({
            "openalex_id": w["id"].split("/")[-1],
            "title": w.get("title") or "Untitled",
            "year": w.get("publication_year"),
            "doi": (w.get("doi") or "").replace("https://doi.org/", "") or None,
            "cited_by": w.get("cited_by_count", 0),
            "pdf_urls": _pdf_candidates(w),
            "landing_pages": _landing_pages(w),
        })
    return works


def safe_name(title: str, wid: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:60]
    return f"{wid}-{slug}.pdf"


def looks_like_pdf(data: bytes) -> bool:
    return data[:5] == b"%PDF-" and len(data) > 10_000


def _try_fetch(client: httpx.Client, url: str) -> bytes | None:
    try:
        resp = client.get(url)
        if resp.status_code == 200 and looks_like_pdf(resp.content):
            return resp.content
    except httpx.HTTPError:
        pass
    return None


def download(works: list[dict]) -> list[dict]:
    PAPERS_DIR.mkdir(exist_ok=True)
    saved: list[dict] = []
    client = httpx.Client(headers=HEADERS, timeout=60, follow_redirects=True)
    for w in works:
        if len(saved) >= MAX_PAPERS:
            break
        filename = safe_name(w["title"], w["openalex_id"])
        path = PAPERS_DIR / filename
        if path.exists():
            saved.append({**w, "filename": filename})
            continue
        # Try every OpenAlex location, Semantic Scholar, then landing pages.
        candidates = list(w["pdf_urls"])
        ss = _semantic_scholar_pdf(w["doi"], client)
        if ss and ss not in candidates:
            candidates.append(ss)
        data = None
        for url in candidates:
            data = _try_fetch(client, url)
            if data:
                break
        if data is None:
            for page in w.get("landing_pages", [])[:2]:
                pdf = _pdf_from_landing_page(client, page)
                if pdf:
                    data = _try_fetch(client, pdf)
                    if data:
                        break
        if data is None:
            print(f"  skip (no working PDF): {w['title'][:55]}")
            continue
        path.write_bytes(data)
        saved.append({**w, "filename": filename})
        print(f"  saved: {w['title'][:60]} ({w['year']})")
        time.sleep(0.3)
    client.close()
    return saved


def main() -> None:
    print(f"Downloading open-access papers of {AUTHOR_NAME}...")
    author_id = find_author_id()
    works = list_works(author_id)
    with_pdf = sum(1 for w in works if w["pdf_urls"])
    print(f"  {len(works)} works listed, {with_pdf} with at least one PDF URL")
    saved = download(works)
    MANIFEST.write_text(json.dumps(saved, indent=2, ensure_ascii=False), "utf-8")
    print(f"Wrote {MANIFEST}: {len(saved)} papers downloaded.")
    if len(saved) < 10:
        print("  note: fewer than 10 usable PDFs were available open-access.")


if __name__ == "__main__":
    main()
