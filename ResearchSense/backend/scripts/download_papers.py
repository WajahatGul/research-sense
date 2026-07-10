"""Download open-access papers for every Bahria researcher with publications.

For each researcher that has indexed publications, this script resolves their
OpenAlex author record (Bahria-affiliated), lists their works, and downloads up
to ``PAPERS_PER_AUTHOR`` open-access PDFs (most cited first). Every manifest
entry records the owning ``researcher_id`` so the RAG index and the chat's
source chips attribute each paper to its author.

PDF sources tried in order: every OpenAlex location, Semantic Scholar, then a
scan of landing pages for a direct .pdf link. Existing files are always kept,
so re-runs only add papers.

Run (from backend/):
    python -m scripts.download_papers

Output: papers/*.pdf + papers/manifest.json
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
PAPERS_PER_AUTHOR = 5

BACKEND = Path(__file__).resolve().parent.parent
PAPERS_DIR = BACKEND / "papers"
MANIFEST = PAPERS_DIR / "manifest.json"
RESEARCHERS = BACKEND / "app" / "data" / "researchers.json"


def _clean_name(name: str) -> str:
    return re.sub(r"^(dr|mr|ms|mrs|prof|engr)\.?\s+", "", name.strip(), flags=re.I)


def find_author_id(client: httpx.Client, name: str) -> str | None:
    try:
        r = client.get(f"{API}/authors", params={
            "search": _clean_name(name),
            "filter": f"affiliations.institution.id:{INSTITUTION}",
            "per_page": 3,
        })
        results = r.json().get("results", []) if r.status_code == 200 else []
    except httpx.HTTPError:
        return None
    if not results:
        return None
    return max(results, key=lambda a: a["works_count"])["id"].split("/")[-1]


def _pdf_candidates(work: dict) -> list[str]:
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


def _semantic_scholar_pdf(doi: str | None, client: httpx.Client) -> str | None:
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


def _pdf_from_landing_page(client: httpx.Client, page_url: str) -> str | None:
    try:
        resp = client.get(page_url)
        if resp.status_code != 200:
            return None
        links = re.findall(r"href=[\"']([^\"']*\.pdf[^\"']*)", resp.text, re.I)
        return urljoin(str(resp.url), links[0]) if links else None
    except httpx.HTTPError:
        return None


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


def safe_name(title: str, wid: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:60]
    return f"{wid}-{slug}.pdf"


def author_papers(client: httpx.Client, researcher: dict) -> list[dict]:
    """Download up to PAPERS_PER_AUTHOR PDFs for one researcher."""
    author_id = find_author_id(client, researcher["full_name"])
    if not author_id:
        return []
    try:
        r = client.get(f"{API}/works", params={
            "filter": f"author.id:{author_id}",
            "per_page": 50, "sort": "cited_by_count:desc",
        })
        works = r.json().get("results", []) if r.status_code == 200 else []
    except httpx.HTTPError:
        return []

    saved: list[dict] = []
    new_downloads = 0
    for w in works:
        title = w.get("title") or "Untitled"
        wid = w["id"].split("/")[-1]
        entry = {
            "researcher_id": researcher["researcher_id"],
            "author_name": researcher["full_name"],
            "openalex_id": wid,
            "title": title,
            "year": w.get("publication_year"),
            "doi": (w.get("doi") or "").replace("https://doi.org/", "") or None,
            "cited_by": w.get("cited_by_count", 0),
            "filename": safe_name(title, wid),
        }
        path = PAPERS_DIR / entry["filename"]
        if path.exists():
            saved.append(entry)
            continue
        if new_downloads >= PAPERS_PER_AUTHOR:
            continue
        candidates = _pdf_candidates(w)
        ss = _semantic_scholar_pdf(entry["doi"], client)
        if ss and ss not in candidates:
            candidates.append(ss)
        data = None
        for url in candidates:
            data = _try_fetch(client, url)
            if data:
                break
        if data is None:
            for page in _landing_pages(w)[:2]:
                pdf = _pdf_from_landing_page(client, page)
                if pdf:
                    data = _try_fetch(client, pdf)
                    if data:
                        break
        if data is None:
            continue
        path.write_bytes(data)
        saved.append(entry)
        new_downloads += 1
        time.sleep(0.2)
    return saved


def main() -> None:
    researchers = json.loads(RESEARCHERS.read_text("utf-8"))
    with_pubs = [r for r in researchers if r.get("publication_count")]
    print(f"Downloading open-access papers for {len(with_pubs)} researchers...")
    PAPERS_DIR.mkdir(exist_ok=True)

    manifest: list[dict] = []
    seen_files: set[str] = set()
    client = httpx.Client(headers=HEADERS, timeout=45, follow_redirects=True)
    for i, r in enumerate(with_pubs, start=1):
        papers = author_papers(client, r)
        fresh = [p for p in papers if p["filename"] not in seen_files]
        seen_files.update(p["filename"] for p in fresh)
        manifest.extend(fresh)
        print(f"  [{i:>3}/{len(with_pubs)}] {r['full_name'][:32]:32} {len(fresh)} papers")
        time.sleep(0.2)
    client.close()

    MANIFEST.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), "utf-8")
    print(f"Wrote {MANIFEST}: {len(manifest)} papers for "
          f"{len({p['researcher_id'] for p in manifest})} researchers.")
    print("Next: python -m scripts.build_index")


if __name__ == "__main__":
    main()
