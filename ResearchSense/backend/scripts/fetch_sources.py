"""Supplementary publication sources: Semantic Scholar and Crossref.

OpenAlex (fetch_publications) is primary. These fill gaps for faculty that
OpenAlex covers poorly. All records normalize to one shape; a failing source
returns [] so one outage never aborts the pipeline run.
"""
from __future__ import annotations

import re
import time

import httpx

S2_API = "https://api.semanticscholar.org/graph/v1"
CROSSREF_API = "https://api.crossref.org/works"
HEADERS = {"User-Agent": "ResearchSense/0.1 (mailto:dev@stocklenshq.com)"}
AFFILIATION_HINT = "bahria"  # only accept works whose matched author is Bahria-affiliated

# Country-name -> ISO2 for affiliation strings (extend as needed).
_COUNTRIES = {
    "pakistan": "PK", "united states": "US", "usa": "US", "china": "CN",
    "united kingdom": "GB", "uk": "GB", "england": "GB", "saudi arabia": "SA",
    "united arab emirates": "AE", "uae": "AE", "malaysia": "MY", "turkey": "TR",
    "türkiye": "TR", "germany": "DE", "france": "FR", "italy": "IT",
    "spain": "ES", "canada": "CA", "australia": "AU", "japan": "JP",
    "south korea": "KR", "korea": "KR", "india": "IN", "iran": "IR",
    "egypt": "EG", "qatar": "QA", "oman": "OM", "kuwait": "KW",
    "bangladesh": "BD", "indonesia": "ID", "netherlands": "NL", "norway": "NO",
    "sweden": "SE", "finland": "FI", "denmark": "DK", "switzerland": "CH",
    "austria": "AT", "belgium": "BE", "portugal": "PT", "poland": "PL",
    "czech republic": "CZ", "ireland": "IE", "new zealand": "NZ",
    "singapore": "SG", "thailand": "TH", "vietnam": "VN", "brazil": "BR",
    "mexico": "MX", "south africa": "ZA", "nigeria": "NG", "morocco": "MA",
    "jordan": "JO", "iraq": "IQ", "afghanistan": "AF", "sri lanka": "LK",
    "nepal": "NP", "russia": "RU", "ukraine": "UA", "greece": "GR",
    "hungary": "HU", "romania": "RO", "taiwan": "TW", "hong kong": "HK",
}


def dedupe_key(doi: str | None, title: str, year: int) -> str:
    if doi:
        return "doi:" + doi.strip().lower()
    t = re.sub(r"[^a-z0-9]", "", (title or "").lower())
    return f"ty:{t}:{year or 0}"


def country_from_affiliation(affil: str) -> str | None:
    low = (affil or "").lower()
    for name, code in _COUNTRIES.items():
        if re.search(rf"\b{re.escape(name)}\b", low):
            return code
    return None


def _pub_type(raw: str | None) -> str:
    raw = (raw or "").lower()
    return "conference" if "proceeding" in raw or "conference" in raw else "journal"


def normalize_s2_paper(p: dict) -> dict:
    return {
        "title": (p.get("title") or "").strip(),
        "doi": (p.get("externalIds") or {}).get("DOI"),
        "publication_year": int(p.get("year") or 0),
        "journal_name": p.get("venue") or "Preprint or unindexed venue",
        "publication_type": _pub_type(" ".join(p.get("publicationTypes") or [])),
        "citation_count": int(p.get("citationCount") or 0),
        "authors": [{"full_name": a.get("name", ""),
                     "affiliation": "; ".join(a.get("affiliations") or [])}
                    for a in p.get("authors") or []],
        "topic_names": [f for f in p.get("fieldsOfStudy") or [] if f],
        "source": "semanticscholar",
    }


def normalize_crossref_item(m: dict) -> dict:
    date_parts = ((m.get("issued") or {}).get("date-parts") or [[0]])
    authors = []
    for a in m.get("author") or []:
        name = " ".join(filter(None, [a.get("given"), a.get("family")])).strip()
        affil = "; ".join(x.get("name", "") for x in a.get("affiliation") or [])
        if name:
            authors.append({"full_name": name, "affiliation": affil})
    return {
        "title": " ".join(m.get("title") or []).strip(),
        "doi": m.get("DOI"),
        "publication_year": int(date_parts[0][0] or 0),
        "journal_name": " ".join(m.get("container-title") or [])
                        or "Preprint or unindexed venue",
        "publication_type": _pub_type(m.get("type")),
        "citation_count": int(m.get("is-referenced-by-count") or 0),
        "authors": authors,
        "topic_names": [s for s in m.get("subject") or [] if s],
        "source": "crossref",
    }


def _get(url: str, params: dict) -> dict | None:
    for _ in range(3):
        try:
            r = httpx.get(url, params=params, headers=HEADERS, timeout=40)
            if r.status_code == 200:
                return r.json()
            if r.status_code == 429:
                time.sleep(3)
                continue
        except httpx.HTTPError:
            pass
        time.sleep(1.5)
    return None


def s2_works_for(name: str) -> list[dict]:
    """Semantic Scholar works for a Bahria-affiliated author of this name."""
    data = _get(f"{S2_API}/author/search", {
        "query": name, "fields": "name,affiliations,paperCount"})
    if not data:
        return []
    author = next(
        (a for a in data.get("data") or []
         if any(AFFILIATION_HINT in (af or "").lower()
                for af in a.get("affiliations") or [])), None)
    if author is None:
        return []
    papers = _get(f"{S2_API}/author/{author['authorId']}/papers", {
        "fields": "title,year,externalIds,venue,citationCount,fieldsOfStudy,"
                  "authors.name,authors.affiliations,publicationTypes",
        "limit": 50})
    if not papers:
        return []
    out = [normalize_s2_paper(p) for p in papers.get("data") or []]
    return [r for r in out if r["title"]]


def crossref_works_for(name: str) -> list[dict]:
    """Crossref works matching this author name + Bahria affiliation."""
    data = _get(CROSSREF_API, {
        "query.author": name, "query.affiliation": "Bahria University",
        "rows": 30, "select": "title,DOI,container-title,issued,author,"
                              "is-referenced-by-count,subject,type"})
    if not data:
        return []
    items = (data.get("message") or {}).get("items") or []
    out = []
    for m in items:
        rec = normalize_crossref_item(m)
        if rec["title"] and any(
                AFFILIATION_HINT in a["affiliation"].lower()
                for a in rec["authors"]):
            out.append(rec)
    return out
