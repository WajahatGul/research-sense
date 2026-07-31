# Supervisor Feedback Upgrade Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement all seven supervisor SRS points plus all-department expansion and a fluid clamp-based UI, per the approved spec at `docs/superpowers/specs/2026-07-31-supervisor-feedback-upgrade-design.md`.

**Architecture:** Data-first phases. Phase 1 changes the pipeline scripts (all departments sampled 12/dept/campus, honorific-free names, multi-source publications with topics + institution country codes) and runs the pipeline once in the background. Phase 2 adds backend features that read the new precomputed fields (suggestion sorting/threshold, admin approval with staged embeddings, analytics splits). Phase 3 is frontend (sort dropdown, admin queue, new charts, clamp fluid scale).

**Tech Stack:** FastAPI + Pydantic v2, JSON corpus + SQLite (stdlib sqlite3), fastembed all-MiniLM-L6-v2, httpx, Playwright (scraper); React 18 + TypeScript + @tanstack/react-query + Recharts; pytest (new).

## Global Constraints

- Repo root: `research-sense/` (git). App root: `research-sense/ResearchSense/`. All backend commands run from `ResearchSense/backend/` with the venv at `backend/.venv` activated; frontend commands from `ResearchSense/frontend/`.
- Every source file stays under ~350 lines (repo convention). Routers hold no logic; repositories are the only code touching data sources; components never call `fetch` directly — only `src/api/*`.
- Names display without honorifics everywhere (SRS 3) — stripped once at seed build, never per-display.
- Faculty-portal submissions (PDF upload, DOI, manual) are gated on admin approval; scraped/OpenAlex/Semantic Scholar/Crossref publications and the "study library" flow are NOT gated. Existing submissions are grandfathered (only new submissions enter the pending queue).
- Everything derivable (areas, international flags, suggestion inputs) is computed at pipeline time; request handlers only read, filter, and sort.
- `FACULTY_PER_DEPT = 12` is the only knob for sample size; `None` means everyone.
- Do not commit `backend/app/data/*.json`, `*.npz`, or `papers/` churn produced by pipeline runs unless the task says so; commit code + tests only.
- Windows dev machine; use `python -m pytest` and `python -m scripts.<name>` from `backend/`.

---

### Task 1: Test infrastructure + name/department/expertise normalization module

**Files:**
- Create: `ResearchSense/backend/scripts/normalize.py`
- Create: `ResearchSense/backend/tests/__init__.py` (empty)
- Create: `ResearchSense/backend/tests/test_normalize.py`
- Create: `ResearchSense/backend/requirements-dev.txt`

**Interfaces:**
- Produces: `normalize_name(raw: str) -> str`, `canonical_department(raw: str) -> str`, `split_expertise(raw: str) -> list[str]` — imported by Tasks 2, 3, 5.

- [ ] **Step 1: Create dev requirements and install pytest**

`ResearchSense/backend/requirements-dev.txt`:
```
pytest>=8
```
Run: `cd ResearchSense/backend && .venv/Scripts/python -m pip install -r requirements-dev.txt`

- [ ] **Step 2: Write the failing tests**

`ResearchSense/backend/tests/test_normalize.py`:
```python
from scripts.normalize import canonical_department, normalize_name, split_expertise


class TestNormalizeName:
    def test_strips_dr_prefix(self):
        assert normalize_name("Dr Arshad Farhad") == "Arshad Farhad"

    def test_strips_dotted_title(self):
        assert normalize_name("Dr. Moneeb Gohar") == "Moneeb Gohar"

    def test_strips_stacked_titles(self):
        assert normalize_name("Prof Dr Saad Alvi") == "Saad Alvi"

    def test_strips_engr(self):
        assert normalize_name("Engr. Junaid Nasir") == "Junaid Nasir"

    def test_plain_name_untouched(self):
        assert normalize_name("Abdul Raheem Aleem") == "Abdul Raheem Aleem"

    def test_name_starting_with_titlelike_token_kept(self):
        # "Misbah" starts with "Mis…" but is a real name, not "Miss ..."
        assert normalize_name("Misbah Khan") == "Misbah Khan"

    def test_whitespace_collapsed(self):
        assert normalize_name("  Dr   Ali   Raza ") == "Ali Raza"


class TestCanonicalDepartment:
    def test_title_case_and_trim(self):
        assert canonical_department(" computer science ") == "Computer Science"

    def test_department_of_prefix_removed(self):
        assert canonical_department("Department of Psychology") == "Psychology"

    def test_ampersand_normalized(self):
        assert canonical_department("Humanities & Social Sciences") == \
            "Humanities and Social Sciences"

    def test_empty_becomes_general(self):
        assert canonical_department("") == "General"


class TestSplitExpertise:
    def test_splits_on_commas_and_semicolons(self):
        assert split_expertise("Machine Learning, NLP; Data Mining") == \
            ["Machine Learning", "Natural Language Processing", "Data Mining"]

    def test_canonicalizes_variants(self):
        assert split_expertise("AI and ML") == \
            ["Artificial Intelligence", "Machine Learning"]

    def test_dedupes_case_variants(self):
        assert split_expertise("deep learning, Deep Learning") == ["Deep Learning"]

    def test_empty_gives_empty_list(self):
        assert split_expertise("") == []
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `cd ResearchSense/backend && .venv/Scripts/python -m pytest tests/test_normalize.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'scripts.normalize'`

- [ ] **Step 4: Implement `scripts/normalize.py`**

```python
"""Shared normalization for names, departments, and expertise strings.

Used by the pipeline scripts (scrape, seed, fetch) so every honorific strip
and department/area spelling decision lives in exactly one place (SRS 3, 2).
"""
from __future__ import annotations

import re

_TITLES = r"(?:dr|prof(?:essor)?|engr|mr|mrs|ms|miss|madam|capt|col|maj|brig|lt)"
_TITLE_RE = re.compile(rf"^(?:{_TITLES})\.?\s+", re.I)

# Compound-variant map applied to individual expertise phrases (lowercased).
_AREA_VARIANTS = {
    "ai": "Artificial Intelligence",
    "artificial intelligence": "Artificial Intelligence",
    "ml": "Machine Learning",
    "machine learning": "Machine Learning",
    "dl": "Deep Learning",
    "nlp": "Natural Language Processing",
    "natural language processing": "Natural Language Processing",
    "iot": "Internet of Things",
    "internet of things": "Internet of Things",
    "hci": "Human Computer Interaction",
    "cv": "Computer Vision",
    "cyber security": "Cybersecurity",
    "information security": "Cybersecurity",
    "data sciences": "Data Science",
    "data analytics": "Data Science",
}


def normalize_name(raw: str) -> str:
    """Strip leading honorifics (stacked too) and collapse whitespace."""
    name = re.sub(r"\s+", " ", (raw or "").strip())
    while _TITLE_RE.match(name):
        name = _TITLE_RE.sub("", name, count=1)
    return name.strip()


def canonical_department(raw: str) -> str:
    """One display form per department: no 'Department of', '&'->'and',
    title case, whitespace collapsed. Empty input maps to 'General'."""
    s = re.sub(r"\s+", " ", (raw or "").strip())
    s = re.sub(r"^department\s+of\s+", "", s, flags=re.I)
    s = s.replace("&", "and")
    if not s:
        return "General"
    small = {"of", "and", "in", "for", "the"}
    words = [w if w.lower() in small and i > 0 else w.capitalize()
             for i, w in enumerate(s.split(" "))]
    return " ".join(words)


def split_expertise(raw: str) -> list[str]:
    """Split a free-text expertise string into clean area phrases.

    Splits on , ; / and the word 'and'; canonicalizes known variants;
    dedupes case-insensitively, preserving first-seen order.
    """
    if not (raw or "").strip():
        return []
    parts = re.split(r"[,;/]|\band\b", raw, flags=re.I)
    seen: dict[str, str] = {}
    for p in parts:
        p = re.sub(r"\s+", " ", p).strip(" .")
        if len(p) < 2:
            continue
        canon = _AREA_VARIANTS.get(p.lower())
        if canon is None:
            canon = " ".join(w if w.isupper() else w.capitalize()
                             for w in p.split(" "))
        seen.setdefault(canon.lower(), canon)
    return list(seen.values())
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd ResearchSense/backend && .venv/Scripts/python -m pytest tests/test_normalize.py -v`
Expected: all PASS. If a splitter/canonicalization test fails, fix `normalize.py` (not the test — the tests encode the spec).

- [ ] **Step 6: Commit**

```bash
git add ResearchSense/backend/scripts/normalize.py ResearchSense/backend/tests/ ResearchSense/backend/requirements-dev.txt
git commit -m "feat: shared name/department/expertise normalization + pytest infra"
```

---

### Task 2: Scraper — all departments across all campuses

**Files:**
- Modify: `ResearchSense/backend/scripts/scrape_bahria.py:34-57` (DIRECTORY_JS) and the module docstring at lines 1-8

**Interfaces:**
- Produces: `scripts/scraped_faculty.json` records now spanning every department; each record keeps keys `{id, name, campus, department, designation, areas, email, detail_areas, degree, ...}` exactly as before — only the filter and department normalization change.

- [ ] **Step 1: Replace the computing filter in DIRECTORY_JS**

In `DIRECTORY_JS`, delete the line
```js
  const computing = /computer science|software engineering|computer engineering/i;
```
and change the row guard from
```js
    if (!CAMPUS[code] || !computing.test(dept || '')) continue;
```
to
```js
    if (!CAMPUS[code] || !(dept || '').trim()) continue;
```
Replace the hardcoded department ternary
```js
               department: /software/i.test(dept) ? 'Software Engineering'
                 : /computer engineering/i.test(dept) ? 'Computer Engineering'
                 : 'Computer Science',
```
with the raw value (normalized later in Python, where it is testable):
```js
               department: dept,
```

- [ ] **Step 2: Normalize departments and drop no-department rows in Python**

In `main()`, right after `roster = page.evaluate(DIRECTORY_JS)` add:
```python
        from scripts.normalize import canonical_department

        for person in roster:
            person["department"] = canonical_department(person.get("department", ""))
        roster = [p for p in roster if p["department"] != "General"]
        print(f"  directory: {len(roster)} faculty across all departments")
```
(Replace the old `print(f"  directory: {len(roster)} computing faculty...")` line.)
Update the module docstring: change "This script pulls the computing departments (Computer Science, Software Engineering, Computer Engineering)" to "This script pulls every department".

- [ ] **Step 3: Verify the script still imports cleanly (no live run yet)**

Run: `cd ResearchSense/backend && .venv/Scripts/python -c "import scripts.scrape_bahria as s; print('ok', s.FACULTY_URL)"`
Expected: `ok https://www.bahria.edu.pk/Home/Faculty`. (The live scrape happens in Task 6.)

- [ ] **Step 4: Commit**

```bash
git add ResearchSense/backend/scripts/scrape_bahria.py
git commit -m "feat: scrape every department across all four campuses"
```

---

### Task 3: Seed build — per-department sampling + honorific-free names

**Files:**
- Modify: `ResearchSense/backend/scripts/build_seed.py` (`build_researchers`, add `sample_faculty`, add `FACULTY_PER_DEPT`)
- Create: `ResearchSense/backend/tests/test_build_seed.py`

**Interfaces:**
- Consumes: `normalize_name`, `split_expertise` from `scripts.normalize` (Task 1).
- Produces: `sample_faculty(records: list[dict], cap: int | None) -> list[dict]`; researcher dicts whose `full_name` is honorific-free and whose `expertise_areas` key is `list[str]` (new, alongside the existing `expertise` string). Constant `FACULTY_PER_DEPT: int | None = 12`.

- [ ] **Step 1: Write the failing tests**

`ResearchSense/backend/tests/test_build_seed.py`:
```python
from scripts.build_seed import FACULTY_PER_DEPT, sample_faculty


def _rec(name, campus="Karachi", dept="Psychology", desig="Lecturer", areas="x"):
    return {"name": name, "campus": campus, "department": dept,
            "designation": desig, "areas": areas}


def test_cap_respected_per_campus_department_group():
    recs = [_rec(f"P{i}") for i in range(20)]
    out = sample_faculty(recs, cap=12)
    assert len(out) == 12


def test_groups_are_independent():
    recs = ([_rec(f"A{i}", dept="Law") for i in range(15)]
            + [_rec(f"B{i}", dept="Psychology") for i in range(15)])
    out = sample_faculty(recs, cap=12)
    assert len(out) == 24


def test_prefers_faculty_with_areas_then_seniority():
    recs = [
        _rec("NoAreas Prof", desig="Professor", areas=""),
        _rec("Areas Lect", desig="Lecturer", areas="Clinical Psychology"),
        _rec("Areas Prof", desig="Professor", areas="Neuropsychology"),
    ]
    out = sample_faculty(recs, cap=2)
    names = [r["name"] for r in out]
    assert names == ["Areas Prof", "Areas Lect"]


def test_none_cap_returns_everyone():
    recs = [_rec(f"P{i}") for i in range(30)]
    assert len(sample_faculty(recs, cap=None)) == 30


def test_default_cap_is_twelve():
    assert FACULTY_PER_DEPT == 12
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd ResearchSense/backend && .venv/Scripts/python -m pytest tests/test_build_seed.py -v`
Expected: FAIL — `ImportError: cannot import name 'sample_faculty'`

- [ ] **Step 3: Implement sampling + name normalization in build_seed.py**

Add near the top (after the imports):
```python
from scripts.normalize import normalize_name, split_expertise

FACULTY_PER_DEPT: int | None = 12  # per (campus, department); None = everyone


def sample_faculty(records: list[dict],
                   cap: int | None = FACULTY_PER_DEPT) -> list[dict]:
    """Cap each (campus, department) group, preferring faculty with listed
    research areas, then senior designations — they are the most likely to
    have findable publications. Deterministic (name tiebreak)."""
    if cap is None:
        return records

    def rank(rec: dict):
        has_areas = bool((rec.get("areas") or "").strip())
        d = (rec.get("designation") or "").lower()
        if "professor" in d and "assistant" not in d and "associate" not in d:
            seniority = 3
        elif "associate" in d:
            seniority = 2
        elif "assistant" in d:
            seniority = 1
        else:
            seniority = 0
        return (not has_areas, -seniority, rec.get("name", ""))

    from collections import defaultdict
    groups: dict[tuple, list[dict]] = defaultdict(list)
    for rec in records:
        groups[(rec.get("campus"), rec.get("department"))].append(rec)
    out: list[dict] = []
    for key in sorted(groups):
        out.extend(sorted(groups[key], key=rank)[:cap])
    return out
```
In `build_researchers`, change the loop head from
```python
    for i, rec in enumerate(load_scraped(), start=1):
```
to
```python
    for i, rec in enumerate(sample_faculty(load_scraped()), start=1):
```
and inside the loop set the name and areas through the normalizers:
```python
        name = normalize_name(rec["name"])
```
then use `name` instead of `rec["name"]` for both `"full_name"` and the `_bio(...)` call, and add one new key to the researcher dict (directly after `"expertise": expertise,`):
```python
            "expertise_areas": split_expertise(expertise),
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd ResearchSense/backend && .venv/Scripts/python -m pytest tests/ -v`
Expected: all PASS (normalize tests keep passing too).

- [ ] **Step 5: Commit**

```bash
git add ResearchSense/backend/scripts/build_seed.py ResearchSense/backend/tests/test_build_seed.py
git commit -m "feat: sample 12 faculty per department/campus; strip honorifics at seed"
```

---

### Task 4: Multi-source publication fetch helpers (Semantic Scholar + Crossref)

**Files:**
- Create: `ResearchSense/backend/scripts/fetch_sources.py`
- Create: `ResearchSense/backend/tests/test_fetch_sources.py`

**Interfaces:**
- Produces (consumed by Task 5):
  - `dedupe_key(doi: str | None, title: str, year: int) -> str`
  - `country_from_affiliation(affil: str) -> str | None` (ISO-2 code or None)
  - `s2_works_for(name: str) -> list[dict]` and `crossref_works_for(name: str) -> list[dict]` — both return normalized dicts: `{"title", "doi", "publication_year", "journal_name", "publication_type", "citation_count", "authors": [{"full_name", "affiliation"}], "topic_names": [str], "source": "semanticscholar"|"crossref"}`
- Network functions follow the existing `_get` retry pattern from `fetch_publications.py`; a failing source returns `[]`, never raises.

- [ ] **Step 1: Write the failing tests (pure logic only — no network)**

`ResearchSense/backend/tests/test_fetch_sources.py`:
```python
from scripts.fetch_sources import (country_from_affiliation, dedupe_key,
                                   normalize_s2_paper, normalize_crossref_item)


def test_dedupe_prefers_doi():
    assert dedupe_key("10.1/ABC", "Any Title", 2020) == "doi:10.1/abc"


def test_dedupe_falls_back_to_title_year():
    assert dedupe_key(None, "A Study: of Things!", 2021) == "ty:astudyofthings:2021"


def test_country_from_affiliation_matches_country_name():
    assert country_from_affiliation("MIT, Cambridge, United States") == "US"
    assert country_from_affiliation("Bahria University, Islamabad, Pakistan") == "PK"


def test_country_from_affiliation_unknown_is_none():
    assert country_from_affiliation("Some Lab") is None


def test_normalize_s2_paper_shapes_record():
    raw = {"title": "T", "year": 2022, "externalIds": {"DOI": "10.2/x"},
           "venue": "VenueX", "citationCount": 3, "fieldsOfStudy": ["Biology"],
           "authors": [{"name": "A B", "affiliations": ["Uni, Pakistan"]}],
           "publicationTypes": ["JournalArticle"]}
    rec = normalize_s2_paper(raw)
    assert rec["doi"] == "10.2/x" and rec["publication_year"] == 2022
    assert rec["topic_names"] == ["Biology"]
    assert rec["authors"][0]["affiliation"] == "Uni, Pakistan"
    assert rec["source"] == "semanticscholar"


def test_normalize_crossref_item_shapes_record():
    raw = {"title": ["T2"], "DOI": "10.3/y", "container-title": ["J"],
           "issued": {"date-parts": [[2019]]}, "is-referenced-by-count": 5,
           "subject": ["Economics"], "type": "journal-article",
           "author": [{"given": "C", "family": "D",
                       "affiliation": [{"name": "X University, Turkey"}]}]}
    rec = normalize_crossref_item(raw)
    assert rec["doi"] == "10.3/y" and rec["publication_year"] == 2019
    assert rec["topic_names"] == ["Economics"]
    assert rec["authors"][0]["full_name"] == "C D"
    assert rec["source"] == "crossref"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd ResearchSense/backend && .venv/Scripts/python -m pytest tests/test_fetch_sources.py -v`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement `scripts/fetch_sources.py`**

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd ResearchSense/backend && .venv/Scripts/python -m pytest tests/test_fetch_sources.py -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add ResearchSense/backend/scripts/fetch_sources.py ResearchSense/backend/tests/test_fetch_sources.py
git commit -m "feat: Semantic Scholar + Crossref supplementary publication sources"
```

---

### Task 5: fetch_publications — topics, institutions, international flags, derived areas, dynamic topics.json

**Files:**
- Modify: `ResearchSense/backend/scripts/fetch_publications.py`
- Modify: `ResearchSense/backend/app/schemas/publication.py` (add fields)
- Modify: `ResearchSense/backend/app/schemas/researcher.py` (add fields)
- Create: `ResearchSense/backend/tests/test_fetch_enrichment.py`

**Interfaces:**
- Consumes: Task 4's `s2_works_for`, `crossref_works_for`, `dedupe_key`, `country_from_affiliation`; Task 3's `expertise_areas` on researcher records.
- Produces (new persisted fields):
  - publication: `topic_names: list[str]`, `coauthor_institutions: [{"name": str, "country": str|None}]`, `international: bool`
  - researcher: `research_areas: list[str]` (top-5 hybrid), `international_collaborations: [{"institution": str, "country": str}]`
  - `topics.json` rebuilt dynamically from the union of all `research_areas`
- Pure functions (unit-tested): `expertise_field_guard(work_topic_names, expertise_text) -> bool`, `derive_research_areas(researcher, linked_pubs, top_n=5) -> list[str]`, `international_of(institutions) -> bool`, `merge_supplementary(primary, extra) -> list[dict]`

- [ ] **Step 1: Write the failing tests**

`ResearchSense/backend/tests/test_fetch_enrichment.py`:
```python
from scripts.fetch_publications import (derive_research_areas,
                                        expertise_field_guard,
                                        international_of,
                                        merge_supplementary)


def test_field_guard_matches_on_token_overlap():
    assert expertise_field_guard(["Machine Learning"], "machine learning, vision")


def test_field_guard_includes_department_text():
    assert expertise_field_guard(["Clinical Psychology"], "psychology")


def test_field_guard_rejects_disjoint_fields():
    assert not expertise_field_guard(["Organic Chemistry"], "machine learning")


def test_field_guard_empty_expertise_rejects():
    assert not expertise_field_guard(["Anything"], "")


def test_international_true_for_non_pk():
    assert international_of([{"name": "MIT", "country": "US"}])


def test_international_false_for_pk_only_or_unknown():
    assert not international_of([{"name": "Bahria", "country": "PK"},
                                 {"name": "X", "country": None}])
    assert not international_of([])


def test_derive_areas_from_publication_topics():
    r = {"expertise_areas": ["Old Area"]}
    pubs = [{"topic_names": ["Neuroscience", "Psychiatry"]},
            {"topic_names": ["Neuroscience"]}]
    areas = derive_research_areas(r, pubs)
    assert areas[0] == "Neuroscience" and "Psychiatry" in areas


def test_derive_areas_falls_back_to_expertise():
    r = {"expertise_areas": ["Corporate Law", "Taxation"]}
    assert derive_research_areas(r, []) == ["Corporate Law", "Taxation"]


def test_merge_supplementary_dedupes_by_doi_then_title():
    primary = [{"doi": "10.1/a", "title": "T1", "publication_year": 2020}]
    extra = [{"doi": "10.1/A", "title": "Other", "publication_year": 2020},
             {"doi": None, "title": "T1!", "publication_year": 2020},
             {"doi": None, "title": "Brand New", "publication_year": 2021}]
    merged = merge_supplementary(primary, extra)
    titles = [p["title"] for p in merged]
    assert titles == ["T1", "Brand New"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd ResearchSense/backend && .venv/Scripts/python -m pytest tests/test_fetch_enrichment.py -v`
Expected: FAIL — names not importable.

- [ ] **Step 3: Add the pure functions to fetch_publications.py**

Add after the existing helpers (before `main`):
```python
from scripts.fetch_sources import (country_from_affiliation, crossref_works_for,
                                   dedupe_key, s2_works_for)


def expertise_field_guard(work_topic_names: list[str], expertise_text: str) -> bool:
    """Attribution guard for ALL departments: the work's topic words must
    overlap the researcher's expertise/department words. Empty expertise
    rejects (an anchored internal co-authorship may still link, as before)."""
    if not (expertise_text or "").strip():
        return False
    exp = set(re.findall(r"[a-z]{4,}", expertise_text.lower()))
    work = {t for name in work_topic_names
            for t in re.findall(r"[a-z]{4,}", (name or "").lower())}
    return bool(exp & work)


def international_of(institutions: list[dict]) -> bool:
    return any((i.get("country") or "") not in ("", "PK", None) and
               i.get("country") != "PK" for i in institutions)


def derive_research_areas(researcher: dict, linked_pubs: list[dict],
                          top_n: int = 5) -> list[str]:
    """Hybrid areas: most frequent topic names across the researcher's actual
    publications; fallback to their cleaned directory expertise."""
    from collections import Counter
    counts: Counter = Counter()
    for p in linked_pubs:
        for name in p.get("topic_names") or []:
            counts[name] += 1
    ranked = [name for name, _ in counts.most_common(top_n)]
    if ranked:
        return ranked
    return (researcher.get("expertise_areas") or [])[:top_n]


def merge_supplementary(primary: list[dict], extra: list[dict]) -> list[dict]:
    seen = {dedupe_key(p.get("doi"), p.get("title", ""),
                       p.get("publication_year", 0)) for p in primary}
    out = list(primary)
    for p in extra:
        key = dedupe_key(p.get("doi"), p.get("title", ""),
                         p.get("publication_year", 0))
        if key in seen:
            continue
        seen.add(key)
        out.append(p)
    return out
```

- [ ] **Step 4: Run the pure-function tests**

Run: `cd ResearchSense/backend && .venv/Scripts/python -m pytest tests/test_fetch_enrichment.py -v`
Expected: all PASS.

- [ ] **Step 5: Wire enrichment into `main()`**

Inside the per-work loop of `main()`, after `work_topics = topics_for_work(...)`:
```python
        oa_topic_names = [t.get("display_name", "")
                          for t in (w.get("topics") or [])[:3]]
        institutions: list[dict] = []
        for a in authorships:
            for inst in a.get("institutions") or []:
                entry = {"name": inst.get("display_name", ""),
                         "country": inst.get("country_code")}
                if entry["name"] and entry not in institutions:
                    institutions.append(entry)
```
Replace BOTH field-guard call sites with the new guard. Exact-match pass — replace
```python
            link = (rid is not None and author_at_bahria(a)
                    and bool(researcher_topics.get(rid, set()) & work_topic_ids))
```
with
```python
            guard_text = (expertise_of.get(rid, "") if rid is not None else "")
            link = (rid is not None and author_at_bahria(a)
                    and expertise_field_guard(
                        oa_topic_names or [t["topic_name"] for t in work_topics],
                        guard_text))
```
Fuzzy pass — replace
```python
            r_topics = researcher_topics.get(rid, set())
            anchored = bool(matched_ids)
            if r_topics and not (r_topics & work_topic_ids) and not anchored:
                continue
```
with
```python
            anchored = bool(matched_ids)
            if not anchored and not expertise_field_guard(
                    oa_topic_names or [t["topic_name"] for t in work_topics],
                    expertise_of.get(rid, "")):
                continue
```
Add the lookup next to the existing `campus_of` map at the top of `main()` (and delete the now-unused `researcher_topics` map):
```python
    expertise_of = {r["researcher_id"]:
                    f"{r.get('expertise','')} {r.get('department','')}"
                    for r in researchers}
```
Extend the publication dict appended in `main()` with:
```python
            "topic_names": oa_topic_names,
            "coauthor_institutions": institutions,
            "international": international_of(institutions),
```

- [ ] **Step 6: Add the supplementary-source pass in `main()`**

After the OpenAlex loop (before the submitted re-merge), add:
```python
    # Supplementary sources for researchers OpenAlex barely covers.
    covered = {rid for rid, cites in pub_stats.items() if len(cites) >= 3}
    thin = [r for r in researchers if r["researcher_id"] not in covered]
    print(f"  querying Semantic Scholar/Crossref for {len(thin)} researchers")
    extra_norm: list[dict] = []
    for r in thin:
        for rec in (s2_works_for(r["full_name"])
                    + crossref_works_for(r["full_name"])):
            names = rec["topic_names"]
            if not expertise_field_guard(
                    names, f"{r.get('expertise','')} {r.get('department','')}"):
                continue
            insts = []
            for a in rec["authors"]:
                code = country_from_affiliation(a.get("affiliation", ""))
                nm = (a.get("affiliation") or "").split(";")[0].strip()
                if nm and {"name": nm, "country": code} not in insts:
                    insts.append({"name": nm, "country": code})
            extra_norm.append({
                "publication_id": 0,
                "title": clean_title(rec["title"]),
                "abstract": "",
                "doi": rec["doi"],
                "publication_year": rec["publication_year"],
                "journal_name": rec["journal_name"],
                "publication_type": rec["publication_type"],
                "citation_count": rec["citation_count"],
                "campus": r.get("campus", ""),
                "authors": [{"researcher_id":
                             (r["researcher_id"]
                              if _fuzzy_name_match(r["full_name"], a["full_name"])
                              else None),
                             "full_name": a["full_name"], "order": o}
                            for o, a in enumerate(rec["authors"][:12], start=1)],
                "topics": [],
                "topic_names": names,
                "coauthor_institutions": insts,
                "international": international_of(insts),
                "source": rec["source"],
            })
        time.sleep(1.0)  # unauthenticated S2/Crossref rate courtesy
    before = len(publications)
    publications = merge_supplementary(publications, extra_norm)
    for p in publications[before:]:
        p["publication_id"] = 0  # renumbered below
        for a in p["authors"]:
            if a["researcher_id"] is not None:
                pub_stats[a["researcher_id"]].append(p["citation_count"])
    for i, p in enumerate(publications, start=1):
        p["publication_id"] = i
    print(f"  +{len(publications) - before} from supplementary sources")
```

- [ ] **Step 7: Derive researcher areas, international partners, and dynamic topics.json**

After the count-update loop (`for r in researchers: ...`), add:
```python
    # Hybrid research areas + international partners (SRS 2, 6).
    pubs_of: dict[int, list[dict]] = {r["researcher_id"]: [] for r in researchers}
    for p in publications:
        for a in p.get("authors", []):
            rid = a.get("researcher_id")
            if rid in pubs_of:
                pubs_of[rid].append(p)
    for r in researchers:
        mine = pubs_of[r["researcher_id"]]
        r["research_areas"] = derive_research_areas(r, mine)
        partners: list[dict] = []
        for p in mine:
            for inst in p.get("coauthor_institutions", []):
                code = inst.get("country")
                if code and code != "PK":
                    entry = {"institution": inst["name"], "country": code}
                    if entry not in partners:
                        partners.append(entry)
        r["international_collaborations"] = partners

    # Dynamic topic index from the union of derived areas (SRS 2).
    area_names: dict[str, int] = {}
    for r in researchers:
        for name in r["research_areas"]:
            area_names.setdefault(name, len(area_names) + 1)
    topics = [{"topic_id": tid, "topic_name": name, "icon": "sparkles",
               "description": f"Research and expertise in {name}.",
               "source": "derived",
               "researcher_count": sum(1 for r in researchers
                                       if name in r["research_areas"]),
               "publication_count": sum(1 for p in publications
                                        if name in (p.get("topic_names") or []))}
              for name, tid in area_names.items()]
    name_to_id = dict(area_names)
    for r in researchers:
        r["topics"] = [{"topic_id": name_to_id[n], "topic_name": n}
                       for n in r["research_areas"]]
    for p in publications:
        p["topics"] = [{"topic_id": name_to_id[n], "topic_name": n}
                       for n in (p.get("topic_names") or [])
                       if n in name_to_id][:4]
```
Delete the old "Recompute topic counts" loop (it is replaced by the block above).

- [ ] **Step 8: Extend the Pydantic schemas**

`app/schemas/publication.py` — add to the `Publication` model:
```python
    topic_names: list[str] = []
    coauthor_institutions: list[dict] = []
    international: bool = False
```
`app/schemas/researcher.py` — add to `Researcher`:
```python
    research_areas: list[str] = []
```
and to `ResearcherDetail`:
```python
    international_collaborations: list[dict] = []
```

- [ ] **Step 9: Run the full backend test suite + import smoke**

Run: `cd ResearchSense/backend && .venv/Scripts/python -m pytest tests/ -v && .venv/Scripts/python -c "import scripts.fetch_publications; import app.main; print('imports ok')"`
Expected: all tests PASS; `imports ok`.

- [ ] **Step 10: Commit**

```bash
git add ResearchSense/backend/scripts/fetch_publications.py ResearchSense/backend/app/schemas/publication.py ResearchSense/backend/app/schemas/researcher.py ResearchSense/backend/tests/test_fetch_enrichment.py
git commit -m "feat: multi-source fetch with topics, institutions, international flags, derived areas"
```

---

### Task 6: Run the full pipeline in the background

**Files:**
- No source changes. Produces refreshed `scripts/scraped_faculty.json`, `app/data/*.json`, `app/data/rag_index.npz`, `papers/*.pdf`.

**Interfaces:**
- Consumes: Tasks 2–5. Produces: live data every later task's manual verification uses.

- [ ] **Step 1: Launch the pipeline as a background task**

Run (background, from `ResearchSense/backend`, venv python; allow ~1–3 hours):
```bash
.venv/Scripts/python -m playwright install chromium
.venv/Scripts/python -m scripts.scrape_bahria && .venv/Scripts/python -m scripts.build_seed && .venv/Scripts/python -m scripts.fetch_publications && .venv/Scripts/python -m scripts.download_papers && .venv/Scripts/python -m scripts.build_index
```
Launch with the Bash tool's `run_in_background: true` and continue with Task 7 while it runs.

- [ ] **Step 2: When it finishes, verify the outputs**

Run:
```bash
.venv/Scripts/python -c "
import json
rs = json.load(open('app/data/researchers.json', encoding='utf-8'))
ps = json.load(open('app/data/publications.json', encoding='utf-8'))
depts = {r['department'] for r in rs}
titled = [r['full_name'] for r in rs if r['full_name'].lower().startswith(('dr ','dr.','prof','engr','mr ','ms ','mrs '))]
intl = sum(1 for p in ps if p.get('international'))
print(len(rs), 'researchers |', len(depts), 'departments |', len(ps), 'pubs |', intl, 'international |', len(titled), 'titled names')
"
```
Expected: multiple departments (>3), 0 titled names, international > 0. If titled names > 0, the honorific list in `normalize.py` is missing a variant — add it with a test and re-run `build_seed` + `fetch_publications`.

- [ ] **Step 3: Commit the refreshed data**

```bash
git add ResearchSense/backend/scripts/scraped_faculty.json ResearchSense/backend/app/data/ ResearchSense/backend/papers/manifest.json
git commit -m "data: all-department roster (12/dept/campus), multi-source publications, rebuilt index"
```

---

### Task 7: Approval storage — SQLite submissions table + staged-chunk store

**Files:**
- Modify: `ResearchSense/backend/app/repositories/accounts.py` (`_SCHEMA` + new methods)
- Create: `ResearchSense/backend/app/services/staging.py`
- Create: `ResearchSense/backend/tests/test_approval_store.py`

**Interfaces:**
- Produces (consumed by Tasks 8, 9):
  - `AccountStore.create_submission(kind: str, researcher_id: int, title: str, record_json: str) -> int`
  - `AccountStore.pending_submissions() -> list[dict]`, `AccountStore.get_submission(sub_id: int) -> dict | None`
  - `AccountStore.set_submission_status(sub_id: int, status: str, note: str | None = None) -> None`
  - `AccountStore.submissions_for(researcher_id: int) -> list[dict]`
  - `staging.stage_chunks(sub_id: int, chunks: list[dict]) -> int` — embeds now, stores under `app/data/staged/`
  - `staging.merge_staged(sub_id: int) -> int` — appends stored vectors+chunks to the live index (no re-embedding), resets `Retriever`
  - `staging.discard_staged(sub_id: int) -> None`

- [ ] **Step 1: Write the failing tests**

`ResearchSense/backend/tests/test_approval_store.py`:
```python
import json

import numpy as np
import pytest

import app.repositories.accounts as accounts_mod
import app.services.staging as staging
from app.repositories.accounts import AccountStore


@pytest.fixture()
def store(tmp_path, monkeypatch):
    monkeypatch.setattr(accounts_mod, "DB_PATH", tmp_path / "test.db")
    AccountStore._instance = None
    yield AccountStore.instance()
    AccountStore._instance = None


def test_submission_lifecycle(store):
    sid = store.create_submission("publication", 7, "My Paper", '{"title":"My Paper"}')
    pending = store.pending_submissions()
    assert [p["id"] for p in pending] == [sid]
    store.set_submission_status(sid, "approved")
    assert store.pending_submissions() == []
    sub = store.get_submission(sid)
    assert sub["status"] == "approved" and sub["reviewed_at"] is not None


def test_reject_records_note(store):
    sid = store.create_submission("upload", 3, "T", "{}")
    store.set_submission_status(sid, "rejected", note="not a research paper")
    assert store.get_submission(sid)["note"] == "not a research paper"


def test_submissions_for_researcher(store):
    store.create_submission("upload", 3, "A", "{}")
    store.create_submission("upload", 4, "B", "{}")
    mine = store.submissions_for(3)
    assert [m["title"] for m in mine] == ["A"]


def test_stage_merge_roundtrip(tmp_path, monkeypatch):
    # Fake embedder: deterministic 4-dim vectors, no model download in tests.
    class FakeModel:
        def __init__(self, *a, **k): ...
        def embed(self, texts):
            return [np.ones(4, dtype=np.float32) * (i + 1)
                    for i, _ in enumerate(texts)]

    monkeypatch.setattr(staging, "_embedder", lambda: FakeModel())
    monkeypatch.setattr(staging, "STAGED_DIR", tmp_path / "staged")
    monkeypatch.setattr(staging, "INDEX_DIR", tmp_path)
    (tmp_path / "rag_chunks.json").write_text("[]", "utf-8")
    np.savez_compressed(tmp_path / "rag_index.npz",
                        vectors=np.zeros((0, 4), dtype=np.float32))
    monkeypatch.setattr(staging, "_reset_retriever", lambda: None)

    n = staging.stage_chunks(5, [{"text": "hello world chunk", "kind": "paper",
                                  "ref_id": 1, "label": "L"}])
    assert n == 1
    assert (tmp_path / "staged" / "sub-5.json").exists()

    merged = staging.merge_staged(5)
    assert merged == 1
    chunks = json.loads((tmp_path / "rag_chunks.json").read_text("utf-8"))
    assert len(chunks) == 1
    assert not (tmp_path / "staged" / "sub-5.json").exists()


def test_discard_removes_files(tmp_path, monkeypatch):
    monkeypatch.setattr(staging, "STAGED_DIR", tmp_path / "staged")
    (tmp_path / "staged").mkdir()
    (tmp_path / "staged" / "sub-9.json").write_text("[]", "utf-8")
    (tmp_path / "staged" / "sub-9.npz").write_bytes(b"x")
    staging.discard_staged(9)
    assert not list((tmp_path / "staged").iterdir())
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd ResearchSense/backend && .venv/Scripts/python -m pytest tests/test_approval_store.py -v`
Expected: FAIL — missing table methods / missing `app.services.staging`.

- [ ] **Step 3: Extend `_SCHEMA` and add methods in accounts.py**

Append to `_SCHEMA`:
```sql
CREATE TABLE IF NOT EXISTS submissions (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    kind          TEXT NOT NULL,
    researcher_id INTEGER NOT NULL,
    title         TEXT NOT NULL,
    record_json   TEXT NOT NULL,
    status        TEXT NOT NULL DEFAULT 'pending',
    submitted_at  TEXT NOT NULL,
    reviewed_at   TEXT,
    note          TEXT
);
```
Add methods to `AccountStore` (after the uploads section):
```python
    # --- paper submissions (admin approval workflow) ---
    def create_submission(self, kind: str, researcher_id: int, title: str,
                          record_json: str) -> int:
        with self._connect() as con:
            cur = con.execute(
                "INSERT INTO submissions (kind, researcher_id, title,"
                " record_json, submitted_at) VALUES (?, ?, ?, ?, ?)",
                (kind, researcher_id, title, record_json, _now()))
            return int(cur.lastrowid)

    def get_submission(self, sub_id: int) -> dict | None:
        with self._connect() as con:
            row = con.execute("SELECT * FROM submissions WHERE id = ?",
                              (sub_id,)).fetchone()
        return dict(row) if row else None

    def pending_submissions(self) -> list[dict]:
        with self._connect() as con:
            rows = con.execute(
                "SELECT * FROM submissions WHERE status = 'pending' "
                "ORDER BY id").fetchall()
        return [dict(r) for r in rows]

    def set_submission_status(self, sub_id: int, status: str,
                              note: str | None = None) -> None:
        with self._connect() as con:
            con.execute(
                "UPDATE submissions SET status = ?, reviewed_at = ?, note = ?"
                " WHERE id = ?", (status, _now(), note, sub_id))

    def submissions_for(self, researcher_id: int) -> list[dict]:
        with self._connect() as con:
            rows = con.execute(
                "SELECT id, kind, title, status, submitted_at, reviewed_at,"
                " note FROM submissions WHERE researcher_id = ?"
                " ORDER BY id DESC", (researcher_id,)).fetchall()
        return [dict(r) for r in rows]
```

- [ ] **Step 4: Implement `app/services/staging.py`**

```python
"""Staged RAG chunks for papers awaiting admin approval (SRS 7).

Embedding runs at submission time so approval is instant: merge_staged only
appends the precomputed vectors to the live index. Rejection discards the
staged files. Nothing here touches publications.json.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from app.services.rag.retriever import (DATA_DIR as INDEX_DIR, EMBED_MODEL,
                                        MODEL_CACHE, Retriever)

STAGED_DIR = Path(__file__).resolve().parents[1] / "data" / "staged"


def _embedder():
    from fastembed import TextEmbedding  # deferred: slow import
    return TextEmbedding(EMBED_MODEL, cache_dir=str(MODEL_CACHE))


def _reset_retriever() -> None:
    Retriever.reset()


def _paths(sub_id: int) -> tuple[Path, Path]:
    return STAGED_DIR / f"sub-{sub_id}.json", STAGED_DIR / f"sub-{sub_id}.npz"


def stage_chunks(sub_id: int, chunks: list[dict]) -> int:
    """Embed and store chunks for one pending submission. Returns count."""
    if not chunks:
        raise ValueError("Nothing to stage")
    vectors = np.array(
        list(_embedder().embed([c["text"] for c in chunks])), dtype=np.float32)
    vectors /= np.linalg.norm(vectors, axis=1, keepdims=True)
    STAGED_DIR.mkdir(parents=True, exist_ok=True)
    cpath, vpath = _paths(sub_id)
    cpath.write_text(json.dumps(chunks, ensure_ascii=False), "utf-8")
    np.savez_compressed(vpath, vectors=vectors)
    return len(chunks)


def merge_staged(sub_id: int) -> int:
    """Append a submission's staged chunks+vectors to the live index."""
    cpath, vpath = _paths(sub_id)
    if not cpath.exists() or not vpath.exists():
        return 0
    new_chunks = json.loads(cpath.read_text("utf-8"))
    new_vecs = np.load(vpath)["vectors"]
    chunks = json.loads((INDEX_DIR / "rag_chunks.json").read_text("utf-8"))
    existing = np.load(INDEX_DIR / "rag_index.npz")["vectors"]
    chunks.extend(new_chunks)
    (INDEX_DIR / "rag_chunks.json").write_text(
        json.dumps(chunks, ensure_ascii=False), "utf-8")
    base = existing if existing.size else np.zeros((0, new_vecs.shape[1]),
                                                  dtype=np.float32)
    np.savez_compressed(INDEX_DIR / "rag_index.npz",
                        vectors=np.vstack([base, new_vecs]))
    cpath.unlink()
    vpath.unlink()
    _reset_retriever()
    return len(new_chunks)


def discard_staged(sub_id: int) -> None:
    for p in _paths(sub_id):
        p.unlink(missing_ok=True)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd ResearchSense/backend && .venv/Scripts/python -m pytest tests/test_approval_store.py -v`
Expected: all PASS.

- [ ] **Step 6: Commit**

```bash
git add ResearchSense/backend/app/repositories/accounts.py ResearchSense/backend/app/services/staging.py ResearchSense/backend/tests/test_approval_store.py
git commit -m "feat: submissions table + staged-embedding store for approval workflow"
```

---

### Task 8: Gate faculty submissions on approval (service + router)

**Files:**
- Modify: `ResearchSense/backend/app/services/submission_service.py` (`_create`)
- Modify: `ResearchSense/backend/app/routers/papers.py` (`upload_paper`, submit responses, new `GET /mine`)
- Modify: `ResearchSense/backend/app/schemas/submission.py` (add `SubmissionStatus` model; make `SubmissionResult.publication_id` optional)
- Create: `ResearchSense/backend/tests/test_submission_gating.py`

**Interfaces:**
- Consumes: Task 7's `AccountStore` submission methods + `staging.stage_chunks`.
- Produces: `submission_service.publish_record(record: dict) -> dict` (called by Task 9 on approve — it is the old `_persist` + `_bump_researcher_counts` path); `GET /api/papers/mine` returning `list[SubmissionStatus]` with fields `id, kind, title, status, submitted_at, reviewed_at, note`.

- [ ] **Step 1: Write the failing tests**

`ResearchSense/backend/tests/test_submission_gating.py`:
```python
import json

import pytest

import app.repositories.accounts as accounts_mod
import app.services.submission_service as svc
from app.repositories.accounts import AccountStore


@pytest.fixture()
def store(tmp_path, monkeypatch):
    monkeypatch.setattr(accounts_mod, "DB_PATH", tmp_path / "t.db")
    AccountStore._instance = None
    yield AccountStore.instance()
    AccountStore._instance = None


def test_create_stages_instead_of_publishing(store, monkeypatch):
    staged = {}
    monkeypatch.setattr(svc, "_stage_submission",
                        lambda sid, record: staged.setdefault(sid, record))
    published = []
    monkeypatch.setattr(svc, "publish_record",
                        lambda record: published.append(record))
    monkeypatch.setattr(svc, "_link_authors",
                        lambda names, sub: [{"researcher_id": 1,
                                             "full_name": "A", "order": 1}])
    meta = {"title": "Pending Paper", "publication_year": 2024,
            "journal_name": "J", "publication_type": "journal",
            "citation_count": 0, "abstract": "", "doi": None}
    result = svc._create(meta, {"researcher_id": 1, "full_name": "A",
                                "campus": "Karachi"}, source="manual")
    assert result["status"] == "pending"
    assert staged and not published
    sub = store.get_submission(result["submission_id"])
    assert sub["status"] == "pending"
    assert json.loads(sub["record_json"])["title"] == "Pending Paper"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ResearchSense/backend && .venv/Scripts/python -m pytest tests/test_submission_gating.py -v`
Expected: FAIL — `_stage_submission` / `publish_record` don't exist; `_create` publishes immediately.

- [ ] **Step 3: Rework `_create` in submission_service.py**

Rename the current publish path and add the staging path. Replace the tail of the module (`_create` plus keep `_persist`, `_bump_researcher_counts`, `_index_chunk` as-is):
```python
def publish_record(record: dict) -> dict:
    """Publish an APPROVED record: publications.json + counts + live chunk.
    This is the pre-approval-era immediate path, now called on approve."""
    record = _persist(record)
    _bump_researcher_counts(record)
    try:
        _index_chunk(record)
    except Exception:  # noqa: BLE001 - the record is saved; index can rebuild
        pass
    return record


def _stage_submission(sub_id: int, record: dict) -> None:
    """Embed the record's fact-card into the staged store (approval-ready)."""
    from app.services import staging

    authors = ", ".join(a["full_name"] for a in record["authors"][:8])
    text = (
        f"Publication: \"{record['title']}\" ({record['publication_year']}), "
        f"{record['publication_type']} in {record['journal_name']}. "
        f"Authors: {authors}. Citations: {record['citation_count']}. "
        f"Campus: {record['campus']}."
    )
    if record.get("doi"):
        text += f" DOI: {record['doi']}."
    staging.stage_chunks(sub_id, [{
        "text": text, "kind": "publication", "ref_id": None,
        "label": f"{record['title'][:70]} ({record['publication_year']})",
    }])


def _create(meta: dict, submitter: dict, source: str) -> dict:
    """Store the submission as PENDING; admins publish it (SRS 7)."""
    from app.repositories.accounts import AccountStore

    authors = _link_authors(meta.get("authors", []), submitter)
    if not any(a.get("researcher_id") == submitter["researcher_id"]
               for a in authors):
        authors.append({
            "researcher_id": submitter["researcher_id"],
            "full_name": submitter["full_name"],
            "order": len(authors) + 1,
        })
    record = {
        "publication_id": 0,  # assigned when published on approval
        "title": meta["title"],
        "abstract": meta.get("abstract", ""),
        "doi": meta.get("doi"),
        "publication_year": meta["publication_year"],
        "journal_name": meta["journal_name"],
        "publication_type": meta["publication_type"],
        "citation_count": meta.get("citation_count", 0),
        "campus": submitter.get("campus", ""),
        "authors": authors,
        "topics": _topics_for(meta["title"], meta.get("abstract", ""),
                              meta.get("concepts")),
        "source": source,
    }
    sub_id = AccountStore.instance().create_submission(
        "publication", submitter["researcher_id"], record["title"],
        json.dumps(record, ensure_ascii=False))
    try:
        _stage_submission(sub_id, record)
    except Exception:  # noqa: BLE001 - approval merge falls back to rebuild
        pass
    return {"status": "pending", "submission_id": sub_id,
            "title": record["title"],
            "publication_year": record["publication_year"],
            "journal_name": record["journal_name"]}
```
The old `_index_chunk` chunk format used `"ref_id": record["publication_id"]`; staged fact-cards use `ref_id: None` because the id is assigned at publish time — Task 9 rewrites the label/ref on merge? No: keep it simple and correct — on approve, Task 9 publishes the record first (getting the real id), then calls `staging.merge_staged`; the fact-card text (title/year/venue/authors) is what retrieval matches on, and `ref_id` is only used for source-chip attribution of researcher-kind chunks, so `None` is acceptable for these cards (the existing library flow already uses `ref_id: None`).

- [ ] **Step 4: Gate the PDF upload path in papers.py**

Replace the body of `upload_paper` after the PDF is written to disk (`path.write_bytes(data)`), removing the immediate `indexer.add_paper` call:
```python
    from app.core.deps import get_researcher_service
    from app.repositories.accounts import AccountStore as _Store
    from app.services import staging
    from app.services.rag import indexer

    researcher = get_researcher_service().get(researcher_id)
    author = researcher.full_name if researcher else "a university researcher"
    try:
        text = indexer.extract_pdf_text(path)
    except ValueError as exc:
        path.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail=str(exc))
    header = f"From the paper \"{title.strip()}\" by {author}: "
    chunks = [{"text": header + piece, "kind": "paper",
               "ref_id": researcher_id,
               "label": f"Paper: {title.strip()[:70]} (uploaded)"}
              for piece in indexer._split(text)]
    if not chunks:
        path.unlink(missing_ok=True)
        raise HTTPException(status_code=400,
                            detail="The PDF is too short to index")
    import json as _json
    sub_id = _Store.instance().create_submission(
        "upload", researcher_id, title.strip(),
        _json.dumps({"filename": filename, "title": title.strip()}))
    staging.stage_chunks(sub_id, chunks)
    store.record_upload(researcher_id, title.strip(), filename)
    return {"status": "pending", "submission_id": sub_id,
            "message": "Your paper is awaiting admin approval. It will be "
                       "searchable the moment it is approved."}
```
Update the DOI and manual submit endpoints' `SubmissionResult` returns: `publication_id=None`, and messages
`"Submitted for admin approval. It will appear on your profile and in Publications once approved."`
In `app/schemas/submission.py` change `publication_id: int` to `publication_id: int | None = None` on `SubmissionResult`, and add:
```python
class SubmissionStatus(BaseModel):
    id: int
    kind: str
    title: str
    status: str
    submitted_at: str
    reviewed_at: str | None = None
    note: str | None = None
```

- [ ] **Step 5: Add `GET /api/papers/mine`**

In `papers.py`:
```python
@router.get("/mine", response_model=list[SubmissionStatus])
def my_submissions(token_payload: dict = Depends(current_user)):
    """The signed-in researcher's paper submissions with approval status."""
    researcher = _submitting_researcher(token_payload)
    return AccountStore.instance().submissions_for(researcher["researcher_id"])
```
(Import `SubmissionStatus` from `app.schemas.submission`.)

- [ ] **Step 6: Run the tests**

Run: `cd ResearchSense/backend && .venv/Scripts/python -m pytest tests/ -v`
Expected: all PASS.

- [ ] **Step 7: Commit**

```bash
git add ResearchSense/backend/app/services/submission_service.py ResearchSense/backend/app/routers/papers.py ResearchSense/backend/app/schemas/submission.py ResearchSense/backend/tests/test_submission_gating.py
git commit -m "feat: faculty paper submissions now pend admin approval with staged embeddings"
```

---

### Task 9: Admin queue endpoints (pending / approve / reject)

**Files:**
- Modify: `ResearchSense/backend/app/routers/admin.py`
- Create: `ResearchSense/backend/tests/test_admin_approval.py`

**Interfaces:**
- Consumes: `AccountStore` submission methods (Task 7), `staging.merge_staged` / `discard_staged` (Task 7), `submission_service.publish_record` (Task 8).
- Produces: `GET /api/admin/papers/pending` → `list[{id, kind, researcher_id, title, submitted_at, record}]`; `POST /api/admin/papers/{sub_id}/approve` → `{status}`; `POST /api/admin/papers/{sub_id}/reject` body `{note?: str}` → `{status}`. Consumed by Task 14's frontend.

- [ ] **Step 1: Write the failing tests**

`ResearchSense/backend/tests/test_admin_approval.py`:
```python
import json

import pytest
from fastapi.testclient import TestClient

import app.repositories.accounts as accounts_mod
from app.repositories.accounts import AccountStore


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(accounts_mod, "DB_PATH", tmp_path / "t.db")
    AccountStore._instance = None
    from app.core import security
    from app.main import app
    app.dependency_overrides[security.current_admin] = lambda: {"role": "admin"}
    yield TestClient(app)
    app.dependency_overrides.clear()
    AccountStore._instance = None


def _pend(title="P1"):
    return AccountStore.instance().create_submission(
        "publication", 1, title, json.dumps({"title": title, "authors": []}))


def test_pending_queue_lists_submissions(client):
    _pend("Queued Paper")
    rows = client.get("/api/admin/papers/pending").json()
    assert [r["title"] for r in rows] == ["Queued Paper"]
    assert rows[0]["record"]["title"] == "Queued Paper"


def test_approve_publishes_and_merges(client, monkeypatch):
    import app.routers.admin as admin_mod
    published, merged = [], []
    monkeypatch.setattr(admin_mod.submission_service, "publish_record",
                        lambda rec: published.append(rec) or {**rec, "publication_id": 99})
    monkeypatch.setattr(admin_mod.staging, "merge_staged",
                        lambda sid: merged.append(sid) or 1)
    sid = _pend()
    resp = client.post(f"/api/admin/papers/{sid}/approve")
    assert resp.status_code == 200
    assert published and merged == [sid]
    assert AccountStore.instance().get_submission(sid)["status"] == "approved"


def test_approve_is_idempotent(client, monkeypatch):
    import app.routers.admin as admin_mod
    monkeypatch.setattr(admin_mod.submission_service, "publish_record",
                        lambda rec: {**rec, "publication_id": 1})
    monkeypatch.setattr(admin_mod.staging, "merge_staged", lambda sid: 1)
    sid = _pend()
    client.post(f"/api/admin/papers/{sid}/approve")
    resp = client.post(f"/api/admin/papers/{sid}/approve")
    assert resp.status_code == 200 and resp.json()["status"] == "approved"


def test_reject_discards_staged(client, monkeypatch):
    import app.routers.admin as admin_mod
    discarded = []
    monkeypatch.setattr(admin_mod.staging, "discard_staged",
                        lambda sid: discarded.append(sid))
    sid = _pend()
    resp = client.post(f"/api/admin/papers/{sid}/reject",
                       json={"note": "duplicate"})
    assert resp.status_code == 200
    assert discarded == [sid]
    sub = AccountStore.instance().get_submission(sid)
    assert sub["status"] == "rejected" and sub["note"] == "duplicate"


def test_upload_kind_approval_merges_without_publishing(client, monkeypatch):
    import app.routers.admin as admin_mod
    published, merged = [], []
    monkeypatch.setattr(admin_mod.submission_service, "publish_record",
                        lambda rec: published.append(rec))
    monkeypatch.setattr(admin_mod.staging, "merge_staged",
                        lambda sid: merged.append(sid) or 3)
    sid = AccountStore.instance().create_submission(
        "upload", 2, "PDF Paper", json.dumps({"filename": "f.pdf"}))
    client.post(f"/api/admin/papers/{sid}/approve")
    assert merged == [sid] and not published
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd ResearchSense/backend && .venv/Scripts/python -m pytest tests/test_admin_approval.py -v`
Expected: FAIL — 404s (routes don't exist).

- [ ] **Step 3: Add the endpoints to admin.py**

```python
import json

from pydantic import BaseModel

from app.services import staging, submission_service


class RejectBody(BaseModel):
    note: str | None = None


@router.get("/papers/pending")
def pending_papers():
    """Papers awaiting review, oldest first, with the full record payload."""
    out = []
    for s in AccountStore.instance().pending_submissions():
        out.append({"id": s["id"], "kind": s["kind"],
                    "researcher_id": s["researcher_id"], "title": s["title"],
                    "submitted_at": s["submitted_at"],
                    "record": json.loads(s["record_json"])})
    return out


@router.post("/papers/{sub_id}/approve")
def approve_paper(sub_id: int):
    """Publish a pending paper and merge its staged chunks (instant go-live).
    Idempotent: an already-approved paper is a no-op."""
    store = AccountStore.instance()
    sub = store.get_submission(sub_id)
    if sub is None:
        raise HTTPException(status_code=404, detail="No such submission")
    if sub["status"] == "approved":
        return {"status": "approved", "id": sub_id}
    if sub["kind"] == "publication":
        submission_service.publish_record(json.loads(sub["record_json"]))
    staging.merge_staged(sub_id)
    store.set_submission_status(sub_id, "approved")
    return {"status": "approved", "id": sub_id}


@router.post("/papers/{sub_id}/reject")
def reject_paper(sub_id: int, body: RejectBody):
    """Reject a pending paper; its staged chunks are discarded."""
    store = AccountStore.instance()
    if store.get_submission(sub_id) is None:
        raise HTTPException(status_code=404, detail="No such submission")
    staging.discard_staged(sub_id)
    store.set_submission_status(sub_id, "rejected", note=body.note)
    return {"status": "rejected", "id": sub_id}
```
Add `HTTPException` to the fastapi import at the top of admin.py.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd ResearchSense/backend && .venv/Scripts/python -m pytest tests/ -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add ResearchSense/backend/app/routers/admin.py ResearchSense/backend/tests/test_admin_approval.py
git commit -m "feat: admin pending-paper queue with approve/reject"
```

---

### Task 10: Collaborator suggestions — relevance score, signal threshold, sort param

**Files:**
- Modify: `ResearchSense/backend/app/repositories/mock/researchers.py` (`_collaborators_for` + new `collaborators` method)
- Modify: `ResearchSense/backend/app/repositories/base.py` (add abstract `collaborators`)
- Modify: `ResearchSense/backend/app/services/researcher_service.py` (pass-through)
- Modify: `ResearchSense/backend/app/routers/researchers.py` (new endpoint)
- Modify: `ResearchSense/backend/app/schemas/researcher.py` (add `relevance: float`, `international: bool` to `CollaborationSuggestion`)
- Create: `ResearchSense/backend/tests/test_collaborators.py`

**Interfaces:**
- Produces: `GET /api/researchers/{id}/collaborators?sort=relevance|shared_areas|coauthored|name|campus` → `list[CollaborationSuggestion]`; suggestion payload gains `relevance` (float) and `international` (bool — the pair has co-authored an international paper or the candidate has international collaborations). Detail embedding stays (default relevance order) so existing consumers keep working. Consumed by Task 13.

- [ ] **Step 1: Write the failing tests**

`ResearchSense/backend/tests/test_collaborators.py`:
```python
import pytest

from app.repositories.mock.researchers import MockResearcherRepository, score_of


def _r(rid, name, topics, campus="Karachi", intl=None):
    return {"researcher_id": rid, "full_name": name, "designation": "Lecturer",
            "department": "CS", "campus": campus,
            "topics": [{"topic_id": t, "topic_name": f"T{t}"} for t in topics],
            "international_collaborations": intl or []}


class FakeRepo(MockResearcherRepository):
    def __init__(self, researchers, publications):
        self._rs, self._ps = researchers, publications
    def _all(self):
        return self._rs
    def _pubs(self):
        return self._ps


@pytest.fixture()
def repo():
    rs = [_r(1, "Alpha", [1, 2]),
          _r(2, "Beta", [1, 2], campus="Lahore"),
          _r(3, "Gamma", [2]),
          _r(4, "Delta", [9]),           # no shared signal with Alpha
          _r(5, "Echo", [1], intl=[{"institution": "MIT", "country": "US"}])]
    ps = [{"authors": [{"researcher_id": 1}, {"researcher_id": 3}],
           "international": False}]
    return FakeRepo(rs, ps)


def test_no_signal_candidates_are_dropped(repo):
    ids = [c["researcher_id"] for c in repo.collaborators(1)]
    assert 4 not in ids


def test_coauthor_outranks_shared_areas_by_default(repo):
    ids = [c["researcher_id"] for c in repo.collaborators(1)]
    assert ids[0] == 3  # past co-author first


def test_rare_shared_area_scores_higher_than_common():
    # Topic 5 is shared by 2 people; topic 1 by four -> rarer wins.
    rs = [_r(1, "A", [1, 5]), _r(2, "B", [1]), _r(3, "C", [1]),
          _r(4, "D", [1]), _r(5, "E", [5])]
    repo = FakeRepo(rs, [])
    freq = {1: 4, 5: 2}
    assert score_of(copub=0, shared_ids={5}, topic_freq=freq) > \
           score_of(copub=0, shared_ids={1}, topic_freq=freq)


def test_sort_by_name(repo):
    names = [c["full_name"] for c in repo.collaborators(1, sort="name")]
    assert names == sorted(names)


def test_sort_by_coauthored(repo):
    rows = repo.collaborators(1, sort="coauthored")
    assert rows[0]["researcher_id"] == 3


def test_international_flag_from_candidate_collabs(repo):
    echo = next(c for c in repo.collaborators(1)
                if c["researcher_id"] == 5)
    assert echo["international"] is True
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd ResearchSense/backend && .venv/Scripts/python -m pytest tests/test_collaborators.py -v`
Expected: FAIL — `score_of` / `collaborators` / `_pubs` missing.

- [ ] **Step 3: Implement scoring + sorting in mock/researchers.py**

Add a module-level function and rework `_collaborators_for`:
```python
def score_of(copub: int, shared_ids: set, topic_freq: dict) -> float:
    """Relevance: co-authored papers dominate; shared areas count more when
    they are rare (a shared niche beats a shared 'Machine Learning')."""
    area_score = sum(1.0 / max(topic_freq.get(t, 1), 1) for t in shared_ids)
    return copub * 5.0 + area_score
```
In the class, add a publications accessor (so tests can fake it) and the public method:
```python
    def _pubs(self) -> list[dict]:
        return loader.load("publications")

    def collaborators(self, researcher_id: int,
                      sort: str = "relevance") -> list[dict]:
        rec = next((r for r in self._all()
                    if r["researcher_id"] == researcher_id), None)
        if rec is None:
            return []
        rows = self._collaborators_for(rec)
        keys = {
            "relevance": lambda c: -c["relevance"],
            "shared_areas": lambda c: (-c["shared_count"], -c["relevance"]),
            "coauthored": lambda c: (-c["copublications"], -c["relevance"]),
            "name": lambda c: c["full_name"],
            "campus": lambda c: (c["campus"], -c["relevance"]),
        }
        rows.sort(key=keys.get(sort, keys["relevance"]))
        return rows
```
Rework `_collaborators_for`: compute `topic_freq` once, use `self._pubs()` in `_copublications_with` (change its `loader.load("publications")` to `self._pubs()`), drop the padding, add the two new fields:
```python
    def _collaborators_for(self, rec: dict) -> list[dict]:
        """Suggest collaborators: past co-authors, then researchers sharing
        (rarity-weighted) research areas. No signal -> not suggested (SRS 4).
        Returns at most 12, relevance-ordered."""
        rid = rec["researcher_id"]
        my_topics = {t["topic_id"]: t["topic_name"] for t in rec.get("topics", [])}
        my_ids = set(my_topics)
        my_campus = rec.get("campus", "")
        copubs = self._copublications_with(rid)
        topic_freq: dict[int, int] = {}
        for r in self._all():
            for t in r.get("topics", []):
                topic_freq[t["topic_id"]] = topic_freq.get(t["topic_id"], 0) + 1

        rows: list[dict] = []
        for other in self._all():
            oid = other["researcher_id"]
            if oid == rid:
                continue
            their_ids = {t["topic_id"] for t in other.get("topics", [])}
            shared_ids = my_ids & their_ids
            copub = copubs.get(oid, 0)
            if not shared_ids and copub == 0:
                continue
            shared_names = sorted(my_topics[i] for i in shared_ids)
            union = my_ids | their_ids
            rows.append(CollaborationSuggestion(
                researcher_id=oid,
                full_name=other["full_name"],
                designation=other.get("designation", ""),
                department=other.get("department", ""),
                campus=other.get("campus", ""),
                similarity_score=round(len(shared_ids) / max(len(union), 1), 2),
                shared_topics=shared_names,
                shared_count=len(shared_ids),
                copublications=copub,
                past_coauthor=copub > 0,
                same_campus=(other.get("campus", "") == my_campus),
                relevance=round(score_of(copub, shared_ids, topic_freq), 3),
                international=bool(other.get("international_collaborations")),
            ).model_dump())
        rows.sort(key=lambda c: -c["relevance"])
        return rows[:12]
```
Add to `CollaborationSuggestion` in `app/schemas/researcher.py`:
```python
    relevance: float = 0.0
    international: bool = False
```
Add to `app/repositories/base.py` `ResearcherRepository`:
```python
    def collaborators(self, researcher_id: int,
                      sort: str = "relevance") -> list[dict]:  # pragma: no cover
        raise NotImplementedError
```
In `app/services/researcher_service.py` add a pass-through `collaborators(researcher_id, sort)`; in `app/routers/researchers.py` add:
```python
@router.get("/{researcher_id}/collaborators",
            response_model=list[CollaborationSuggestion])
def researcher_collaborators(researcher_id: int, sort: str = "relevance"):
    return service.collaborators(researcher_id, sort=sort)
```
(match the router's existing service-access pattern — read the file first and mirror how other endpoints resolve `service`; place the route ABOVE any `"/{researcher_id}"` catch-all so it isn't shadowed).

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd ResearchSense/backend && .venv/Scripts/python -m pytest tests/ -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add ResearchSense/backend/app/repositories/mock/researchers.py ResearchSense/backend/app/repositories/base.py ResearchSense/backend/app/services/researcher_service.py ResearchSense/backend/app/routers/researchers.py ResearchSense/backend/app/schemas/researcher.py ResearchSense/backend/tests/test_collaborators.py
git commit -m "feat: relevance-scored collaborator suggestions with sort options"
```

---

### Task 11: Analytics — department dimension + international split

**Files:**
- Modify: `ResearchSense/backend/app/services/analytics_service.py`
- Modify: `ResearchSense/backend/app/routers/analytics.py` (extend the overview response — read the file first; it exposes `overview()`)
- Create: `ResearchSense/backend/tests/test_analytics.py`

**Interfaces:**
- Produces (added to the `/api/analytics` overview payload): `department_totals: [{department, researchers, publications, citations}]` and `international_split: [{year, international, domestic}]`. Consumed by Task 15.

- [ ] **Step 1: Write the failing tests**

`ResearchSense/backend/tests/test_analytics.py`:
```python
from app.services.analytics_service import AnalyticsService


def test_department_totals_counts_both_sides():
    researchers = [
        {"researcher_id": 1, "campus": "K", "department": "Psychology"},
        {"researcher_id": 2, "campus": "K", "department": "Psychology"},
        {"researcher_id": 3, "campus": "K", "department": "Law"},
    ]
    pubs = [{"campus": "K", "citation_count": 4, "publication_year": 2020,
             "authors": [{"researcher_id": 1}]}]
    rows = AnalyticsService._department_totals(researchers, pubs)
    psych = next(r for r in rows if r["department"] == "Psychology")
    assert psych["researchers"] == 2
    assert psych["publications"] == 1 and psych["citations"] == 4
    law = next(r for r in rows if r["department"] == "Law")
    assert law["publications"] == 0


def test_international_split_by_year():
    pubs = [{"publication_year": 2020, "international": True},
            {"publication_year": 2020, "international": False},
            {"publication_year": 2021, "international": False}]
    rows = AnalyticsService._international_split(pubs)
    assert rows == [{"year": 2020, "international": 1, "domestic": 1},
                    {"year": 2021, "international": 0, "domestic": 1}]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd ResearchSense/backend && .venv/Scripts/python -m pytest tests/test_analytics.py -v`
Expected: FAIL — methods missing.

- [ ] **Step 3: Implement the two aggregations**

Add to `AnalyticsService`:
```python
    @staticmethod
    def _department_totals(researchers: list[dict],
                           publications: list[dict]) -> list[dict]:
        dept_of = {r["researcher_id"]: r.get("department", "")
                   for r in researchers}
        rows: dict[str, dict] = {}
        for r in researchers:
            row = rows.setdefault(r.get("department", ""), {
                "department": r.get("department", ""), "researchers": 0,
                "publications": 0, "citations": 0})
            row["researchers"] += 1
        for p in publications:
            depts = {dept_of[a["researcher_id"]]
                     for a in p.get("authors", [])
                     if a.get("researcher_id") in dept_of}
            for d in depts:
                rows[d]["publications"] += 1
                rows[d]["citations"] += p.get("citation_count", 0)
        return sorted(rows.values(), key=lambda r: -r["publications"])

    @staticmethod
    def _international_split(publications: list[dict]) -> list[dict]:
        from collections import Counter
        intl: Counter = Counter()
        dom: Counter = Counter()
        for p in publications:
            year = p.get("publication_year") or 0
            if year < 2010:
                continue
            (intl if p.get("international") else dom)[year] += 1
        years = sorted(set(intl) | set(dom))
        return [{"year": y, "international": intl[y], "domestic": dom[y]}
                for y in years]
```
And extend `overview()`'s returned dict:
```python
            "department_totals": self._department_totals(researchers, publications),
            "international_split": self._international_split(publications),
```
Mirror the two new keys in whatever response schema `app/routers/analytics.py` declares (read it; if it returns a plain dict, no schema change is needed).

- [ ] **Step 4: Run tests + commit**

Run: `cd ResearchSense/backend && .venv/Scripts/python -m pytest tests/ -v`
Expected: all PASS.
```bash
git add ResearchSense/backend/app/services/analytics_service.py ResearchSense/backend/app/routers/analytics.py ResearchSense/backend/tests/test_analytics.py
git commit -m "feat: analytics department totals + international/domestic split"
```

---

### Task 12: Frontend — types + collaborator sort dropdown

**Files:**
- Modify: `ResearchSense/frontend/src/types/index.ts` (`CollaborationSuggestion` + `ResearcherDetail` + `Researcher` types)
- Modify: `ResearchSense/frontend/src/api/researchers.ts`
- Modify: `ResearchSense/frontend/src/pages/Collaboration.tsx`
- Modify: `ResearchSense/frontend/src/pages/Collaboration.module.css` (reuse the existing `.areaSelect` style for the new dropdown — check the class exists first)

**Interfaces:**
- Consumes: Task 10's endpoint. Produces: `fetchCollaborators(id: number, sort: CollabSort)`; `type CollabSort = "relevance" | "shared_areas" | "coauthored" | "name" | "campus"`.

- [ ] **Step 1: Extend the types**

In `types/index.ts`, add to `CollaborationSuggestion`:
```ts
  relevance: number;
  international: boolean;
```
Add to `Researcher`: `research_areas: string[];` and to `ResearcherDetail`: `international_collaborations: { institution: string; country: string }[];`

- [ ] **Step 2: Add the API client**

In `api/researchers.ts`:
```ts
export type CollabSort =
  | "relevance" | "shared_areas" | "coauthored" | "name" | "campus";

export const fetchCollaborators = (id: number, sort: CollabSort = "relevance") =>
  get<CollaborationSuggestion[]>(`/api/researchers/${id}/collaborators`, { sort });
```
(Import `CollaborationSuggestion` from `../types`.)

- [ ] **Step 3: Add the sort dropdown to Collaboration.tsx**

Add state + query (replacing the `detail.collaborators` source for the list — keep the `fetchResearcher` query for the researcher's name):
```tsx
const SORTS: { key: CollabSort; label: string }[] = [
  { key: "relevance", label: "Most relevant" },
  { key: "shared_areas", label: "Shared research areas" },
  { key: "coauthored", label: "Co-authored papers" },
  { key: "name", label: "Name A–Z" },
  { key: "campus", label: "Campus" },
];
```
```tsx
const [sort, setSort] = useState<CollabSort>("relevance");
const { data: collabRows } = useQuery({
  queryKey: ["collaborators", activeId, sort],
  queryFn: () => fetchCollaborators(activeId as number, sort),
  enabled: activeId != null,
});
const all = collabRows ?? [];
```
Render the dropdown inside the existing `styles.filters` div, before the area select:
```tsx
<select
  className={styles.areaSelect}
  value={sort}
  onChange={(e) => setSort(e.target.value as CollabSort)}
  aria-label="Sort collaborators"
>
  {SORTS.map((s) => (
    <option key={s.key} value={s.key}>{s.label}</option>
  ))}
</select>
```
Remove the `.slice(0, 6)` cap in `filtered` and instead cap at 8 AFTER sorting so the chosen order is what the user sees: `.slice(0, 8)`.

- [ ] **Step 4: Verify with the TypeScript build**

Run: `cd ResearchSense/frontend && npm run build`
Expected: build succeeds with no type errors.

- [ ] **Step 5: Commit**

```bash
git add ResearchSense/frontend/src/types/index.ts ResearchSense/frontend/src/api/researchers.ts ResearchSense/frontend/src/pages/Collaboration.tsx ResearchSense/frontend/src/pages/Collaboration.module.css
git commit -m "feat: collaborator sort dropdown backed by the sort API"
```

---

### Task 13: Frontend — admin pending queue + faculty submission status

**Files:**
- Modify: `ResearchSense/frontend/src/api/auth.ts` (or wherever admin API calls live — locate the existing admin client used by `AdminPanel.tsx` first and follow its pattern)
- Modify: `ResearchSense/frontend/src/features/portal/AdminPanel.tsx`
- Modify: `ResearchSense/frontend/src/features/portal/FacultyDashboard.tsx`
- Modify: `ResearchSense/frontend/src/features/portal/portal.module.css`

**Interfaces:**
- Consumes: Task 9's admin endpoints, Task 8's `GET /api/papers/mine`.

- [ ] **Step 1: Add API clients (same file as the existing admin/account calls)**

```ts
export interface PendingPaper {
  id: number;
  kind: "publication" | "upload";
  researcher_id: number;
  title: string;
  submitted_at: string;
  record: Record<string, unknown>;
}

export interface MySubmission {
  id: number;
  kind: string;
  title: string;
  status: "pending" | "approved" | "rejected";
  submitted_at: string;
  reviewed_at: string | null;
  note: string | null;
}

export const fetchPendingPapers = () =>
  get<PendingPaper[]>("/api/admin/papers/pending");
export const approvePaper = (id: number) =>
  post<{ status: string }>(`/api/admin/papers/${id}/approve`, {});
export const rejectPaper = (id: number, note: string) =>
  post<{ status: string }>(`/api/admin/papers/${id}/reject`, { note });
export const fetchMySubmissions = () =>
  get<MySubmission[]>("/api/papers/mine");
```
(Use the project's existing authenticated `get`/`post` helpers from `api/client.ts` — read that file and match how auth headers are attached.)

- [ ] **Step 2: Add the "Pending papers" section to AdminPanel.tsx**

Read `AdminPanel.tsx` first and mirror its existing section/card structure and react-query usage. The section renders `fetchPendingPapers()` rows: title, kind badge ("Publication" / "PDF upload"), submitter, submitted date, venue/DOI when present in `record`, and two buttons wired to `approvePaper` / `rejectPaper` (reject prompts for an optional note with a small inline text input). Invalidate the `["admin-pending"]` query on success. Empty state: "No papers waiting for review."

- [ ] **Step 3: Show submission status in FacultyDashboard.tsx**

Add a "My submissions" list from `fetchMySubmissions()`: title, kind, and a status chip — pending (gold), approved (green), rejected (red, with the reviewer note underneath when present). Reuse the portal's existing chip/badge styles from `portal.module.css`; add `.statusPending`, `.statusApproved`, `.statusRejected` classes there if none exist.

- [ ] **Step 4: Verify build + manual smoke**

Run: `cd ResearchSense/frontend && npm run build`
Expected: clean build. Then with the backend running (`python -m uvicorn app.main:app --port 8000`) and `npm run dev`: submit a manual publication from the faculty portal, confirm it does NOT appear in Publications, appears in the admin queue, approve it, confirm it now appears in Publications.

- [ ] **Step 5: Commit**

```bash
git add ResearchSense/frontend/src
git commit -m "feat: admin approval queue UI + faculty submission status"
```

---

### Task 14: Frontend — international collaboration surfaces

**Files:**
- Modify: `ResearchSense/frontend/src/pages/ResearcherProfile.tsx` (+ its module.css)
- Modify: `ResearchSense/frontend/src/features/collaboration/NetworkView.tsx` (+ module.css)
- Modify: `ResearchSense/frontend/src/pages/Collaboration.tsx` (pass the flag through)

**Interfaces:**
- Consumes: `ResearcherDetail.international_collaborations` and `CollaborationSuggestion.international` (Tasks 5, 10, 12).

- [ ] **Step 1: Researcher profile — international partners panel**

Read `ResearcherProfile.tsx` and add a section (following its existing panel markup) rendered only when `detail.international_collaborations.length > 0`:
heading "International collaborations", then a list of `{institution} · {country}` rows. Cap at 10 with a "+N more" line.

- [ ] **Step 2: Network view — international badge**

Read `NetworkView.tsx` (it renders collaborator nodes; cross-campus nodes get a gold ring). Add an equivalent visual for `collaborator.international === true` — a small globe glyph or dashed second ring — plus a legend line explaining both markers. Also weight each edge's stroke width by collaboration strength: `strokeWidth = 1 + Math.min(collaborator.copublications, 4)` so proven co-author links read heavier than shared-area-only links (spec §6 edge weighting). Keep colors consistent with the existing palette (`CAMPUS_COLORS` family); do not color by rank.

- [ ] **Step 3: Verify build + visual check**

Run: `cd ResearchSense/frontend && npm run build` — clean.
Manual: open a researcher with `international: true` collaborators and confirm badge + legend render; open a profile with international partners and confirm the panel.

- [ ] **Step 4: Commit**

```bash
git add ResearchSense/frontend/src
git commit -m "feat: international collaboration badges and profile panel"
```

---

### Task 15: Frontend — analytics charts (department + international)

**Files:**
- Modify: `ResearchSense/frontend/src/api/analytics.ts` (add `DepartmentRow`, `IntlRow` to the overview type)
- Modify: `ResearchSense/frontend/src/features/analytics/charts.tsx` (two new chart components)
- Modify: `ResearchSense/frontend/src/pages/Analytics.tsx` (render them)

**Interfaces:**
- Consumes: Task 11's `department_totals` and `international_split` payload keys.

> Before writing any chart code, load the `dataviz` skill and follow its form/palette/mark rules for both charts.

- [ ] **Step 1: Extend the analytics API types**

In `api/analytics.ts` add:
```ts
export interface DepartmentRow {
  department: string;
  researchers: number;
  publications: number;
  citations: number;
}
export interface IntlRow {
  year: number;
  international: number;
  domestic: number;
}
```
and add `department_totals: DepartmentRow[];` and `international_split: IntlRow[];` to the overview response interface.

- [ ] **Step 2: Add the two chart components to charts.tsx**

Following the file's existing Recharts patterns (same `INK`/`GRID`/tooltip constants):
- `DepartmentBars({ data }: { data: DepartmentRow[] })` — horizontal bar chart of publications by department (top 10, `layout="vertical"`, department names as YAxis ticks with enough width, single hue from the existing palette).
- `InternationalTrend({ data }: { data: IntlRow[] })` — stacked bars per year: `domestic` and `international` as two `Bar` series with `stackId="a"`, entity-stable colors (domestic = the neutral `#3b6fd4` family, international = `#1f8a70`), legend on.

- [ ] **Step 3: Render on Analytics.tsx**

Read `Analytics.tsx` and add two new sections following its existing card/section wrapper: "Publications by department" (`DepartmentBars`) and "International vs domestic collaboration" (`InternationalTrend`). Handle the empty case (`data.length === 0`) with the page's existing empty-state pattern.

- [ ] **Step 4: Readability pass on existing charts**

In `charts.tsx`: ensure every chart has visible axis labels or self-evident ticks, legends where >1 series, `Tooltip` formatting consistent (`tooltipStyle` everywhere), and Y axes `allowDecimals={false}` for counts. Fix any chart missing these; make no other changes.

- [ ] **Step 5: Verify build + visual check, then commit**

Run: `cd ResearchSense/frontend && npm run build` — clean. Manual: Analytics page shows both new charts with real pipeline data.
```bash
git add ResearchSense/frontend/src
git commit -m "feat: department and international analytics charts"
```

---

### Task 16: Frontend — fluid clamp scale

**Files:**
- Modify: `ResearchSense/frontend/src/styles/theme.css`
- Modify: any module.css using fixed px paddings on page-level containers (audit; keep the diff focused on scale/spacing, not redesign)

**Interfaces:**
- Produces: fluid `--step-*` and new `--sp-*` custom properties used by all module CSS. Because module CSS already consumes `--step-*`, converting the root scale makes the whole app's typography fluid in one move.

- [ ] **Step 1: Convert the type scale to clamp() and add a space scale**

In `theme.css` replace the `/* Scale */` block:
```css
  /* Fluid type scale: min at ~360px viewports, max at ~1280px */
  --step--1: clamp(0.78rem, 0.74rem + 0.2vw, 0.85rem);
  --step-0: clamp(0.95rem, 0.9rem + 0.3vw, 1.05rem);
  --step-1: clamp(1.08rem, 1rem + 0.5vw, 1.28rem);
  --step-2: clamp(1.28rem, 1.14rem + 0.8vw, 1.6rem);
  --step-3: clamp(1.55rem, 1.3rem + 1.3vw, 2.1rem);
  --step-4: clamp(1.95rem, 1.55rem + 2vw, 2.85rem);
  --step-5: clamp(2.35rem, 1.8rem + 2.9vw, 3.7rem);

  /* Fluid space scale */
  --sp-1: clamp(0.25rem, 0.23rem + 0.1vw, 0.3rem);
  --sp-2: clamp(0.5rem, 0.45rem + 0.2vw, 0.6rem);
  --sp-3: clamp(0.75rem, 0.65rem + 0.4vw, 0.95rem);
  --sp-4: clamp(1rem, 0.85rem + 0.6vw, 1.3rem);
  --sp-5: clamp(1.5rem, 1.25rem + 1vw, 2rem);
  --sp-6: clamp(2rem, 1.6rem + 1.6vw, 2.8rem);
  --sp-7: clamp(3rem, 2.4rem + 2.4vw, 4.2rem);
  --sp-8: clamp(4rem, 3.1rem + 3.5vw, 5.8rem);
```
Update `.container` to the fluid pattern:
```css
.container {
  width: min(100% - 2 * var(--sp-5), var(--container));
  margin: 0 auto;
}
```
(Remove its old `padding: 0 24px`.)

- [ ] **Step 2: Audit module CSS for fixed page-level padding**

Run: `cd ResearchSense/frontend && grep -rn "padding: *[0-9]*px" src/pages/*.module.css src/layout/*.module.css | head -40`
For page/section containers with large fixed paddings (≥16px), replace with the nearest `var(--sp-*)`. Leave small control paddings (buttons, inputs, chips) alone — they don't need to be fluid.

- [ ] **Step 3: Verify at three widths**

Run: `npm run build` — clean. Manual (or Playwright browser): view Home, Researchers, Analytics, Portal at 360px, 768px, 1440px; check for horizontal overflow, unreadably small text, or broken grids. Fix any module grid that overflows by giving its wrapper `overflow-x: auto` (tables) or a `repeat(auto-fit, minmax(...))` column template (card grids).

- [ ] **Step 4: Commit**

```bash
git add ResearchSense/frontend/src
git commit -m "feat: fluid clamp-based type and space scales"
```

---

### Task 17: Refresh job compatibility + docs + final verification

**Files:**
- Verify (modify only if broken): `ResearchSense/backend/app/services/refresh_service.py`, `ResearchSense/backend/scripts/build_index.py`
- Modify: `ResearchSense/README.md` (the app-level README at `research-sense/ResearchSense/README.md`)

**Interfaces:** none new — this is the closing verification gate.

- [ ] **Step 1: Confirm the weekly refresh path carries the new fields**

`refresh_service.run_refresh` calls `fetch_publications.main()` then `build_index.rebuild_preserving_fulltext()`. Read `build_index.py`'s chunk builders (`researcher_chunks`, `publication_chunks`, `collaboration_chunks`) and confirm they read fields that still exist (`topics`, `expertise`, ...). Where a builder references a removed field, update it; also extend `researcher_chunks` to mention `research_areas` and international partners in the fact-card text so the chatbot can answer "who collaborates internationally":
```python
        intl = rec.get("international_collaborations") or []
        if intl:
            partners = "; ".join(f"{i['institution']} ({i['country']})"
                                 for i in intl[:5])
            text += f" International collaborations: {partners}."
```
(Adapt to the builder's actual local variable names after reading it.)

- [ ] **Step 2: Run the whole backend suite + boot smoke**

Run: `cd ResearchSense/backend && .venv/Scripts/python -m pytest tests/ -v`
Expected: all PASS.
Run: `.venv/Scripts/python -c "from fastapi.testclient import TestClient; from app.main import app; c = TestClient(app); r = c.get('/api/researchers?page_size=5'); print(r.status_code, len(r.json().get('items', [])))"`
Expected: `200 5`.

- [ ] **Step 3: Measure the list-endpoint latency target (p95 < 300 ms)**

Run:
```bash
.venv/Scripts/python -c "
import time
from fastapi.testclient import TestClient
from app.main import app
c = TestClient(app)
c.get('/api/researchers')  # warm caches
times = []
for _ in range(40):
    t = time.perf_counter()
    c.get('/api/researchers?page_size=50')
    times.append((time.perf_counter() - t) * 1000)
times.sort()
print(f'p95 = {times[int(len(times)*0.95)]:.1f} ms')
"
```
Expected: p95 < 300. If not, profile before changing anything (the spec's rule: measure, find the actual bottleneck, fix only that).

- [ ] **Step 4: Update the README**

In `ResearchSense/README.md`: update the researcher/department claims ("225 researchers … computing faculty" → all departments, sampled 12 per department/campus, `FACULTY_PER_DEPT` documented), add the admin approval workflow to the Faculty portal / Admin bullets, and mention multi-source publications (OpenAlex + Semantic Scholar + Crossref) and international collaboration analytics.

- [ ] **Step 5: Full-stack manual smoke**

Backend running + `npm run dev`: (1) Researchers page shows multiple departments, no "Dr." prefixes; (2) a profile shows derived research areas + international partners; (3) Collaboration sort dropdown reorders; (4) Analytics shows the two new charts; (5) portal submit → pending → admin approve → visible; (6) chatbot answers a question about an approved submission.

- [ ] **Step 6: Commit**

```bash
git add ResearchSense/README.md ResearchSense/backend/scripts/build_index.py
git commit -m "docs: all-department scope, approval workflow, multi-source pipeline"
```

---

### Task 18: Publications filters — time period, department, paper type (additive)

Modeled on the university's own publications search (Campus / Department / Start–End date / Paper Type). Strictly additive: the existing `q`, `year`, `topic_id`, `author_id`, `campus` params and their UI keep working unchanged.

**Files:**
- Modify: `ResearchSense/backend/app/routers/publications.py:14-28`
- Modify: `ResearchSense/backend/app/services/publication_service.py` (pass-through — read it and mirror the existing param plumbing)
- Modify: `ResearchSense/backend/app/repositories/mock/publications.py` (the filter predicate — read it first; extend its `_matches`-style function)
- Create: `ResearchSense/backend/tests/test_publication_filters.py`
- Modify: `ResearchSense/frontend/src/api/publications.ts`
- Modify: `ResearchSense/frontend/src/pages/Publications.tsx` (+ its module.css — reuse the page's existing select styles)

**Interfaces:**
- Produces: `GET /api/publications` gains `year_from: int | None`, `year_to: int | None`, `department: str | None`, `publication_type: str | None` ("journal" | "conference"). Department matches when ANY linked author belongs to that department (map built once per call from the cached researcher list — `loader.load` is already in-memory-cached, so this stays O(n) per request).

- [ ] **Step 1: Write the failing tests**

`ResearchSense/backend/tests/test_publication_filters.py`:
```python
from app.repositories.mock.publications import publication_matches


def _p(year=2020, ptype="journal", authors=(1,)):
    return {"publication_year": year, "publication_type": ptype,
            "authors": [{"researcher_id": a} for a in authors]}


DEPT_OF = {1: "Computer Science", 2: "Psychology"}


def test_year_range_inclusive():
    assert publication_matches(_p(year=2020), year_from=2019, year_to=2020,
                               dept_of=DEPT_OF)
    assert not publication_matches(_p(year=2018), year_from=2019, year_to=2020,
                                   dept_of=DEPT_OF)


def test_open_ended_ranges():
    assert publication_matches(_p(year=2024), year_from=2020, dept_of=DEPT_OF)
    assert publication_matches(_p(year=2012), year_to=2015, dept_of=DEPT_OF)


def test_department_matches_any_linked_author():
    assert publication_matches(_p(authors=(1, 2)), department="Psychology",
                               dept_of=DEPT_OF)
    assert not publication_matches(_p(authors=(1,)), department="Psychology",
                                   dept_of=DEPT_OF)


def test_publication_type_filter():
    assert publication_matches(_p(ptype="conference"),
                               publication_type="conference", dept_of=DEPT_OF)
    assert not publication_matches(_p(ptype="journal"),
                                   publication_type="conference", dept_of=DEPT_OF)


def test_no_filters_matches_everything():
    assert publication_matches(_p(), dept_of=DEPT_OF)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd ResearchSense/backend && .venv/Scripts/python -m pytest tests/test_publication_filters.py -v`
Expected: FAIL — `publication_matches` not importable.

- [ ] **Step 3: Implement the predicate + plumb the params**

In `app/repositories/mock/publications.py`, add a module-level predicate for the NEW filters (leaving the existing filter logic exactly where it is, and calling this in addition):
```python
def publication_matches(p: dict, *, year_from: int | None = None,
                        year_to: int | None = None,
                        department: str | None = None,
                        publication_type: str | None = None,
                        dept_of: dict[int, str]) -> bool:
    """Additive filters: inclusive year range, any-author department,
    and paper type. None means 'no constraint'."""
    year = p.get("publication_year") or 0
    if year_from is not None and year < year_from:
        return False
    if year_to is not None and year > year_to:
        return False
    if publication_type and p.get("publication_type") != publication_type:
        return False
    if department:
        depts = {dept_of.get(a.get("researcher_id"))
                 for a in p.get("authors", [])}
        if department not in depts:
            return False
    return True
```
In the repository's `list` method, build `dept_of` once from `loader.load("researchers")` and apply `publication_matches` alongside the existing conditions. Thread the four new keyword args through `PublicationService.list` and the router:
```python
    year_from: int | None = None,
    year_to: int | None = None,
    department: str | None = None,
    publication_type: str | None = None,
```
(added to `list_publications`'s signature and passed to `service.list`).

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd ResearchSense/backend && .venv/Scripts/python -m pytest tests/ -v`
Expected: all PASS.

- [ ] **Step 5: Frontend — extend the filter bar**

`api/publications.ts` — add to `PublicationFilters`:
```ts
  year_from?: number;
  year_to?: number;
  department?: string;
  publication_type?: "journal" | "conference";
```
In `Publications.tsx` (read it first; follow its existing filter-state + select markup):
- Add a **Department** select fed by the existing `fetchDepartments()` client from `api/researchers.ts` ("All departments" default).
- Add a **Paper type** select: All / Journal papers / Conference papers.
- Add **From year** and **To year** selects both fed by `fetchPublicationYears()` ("Any" default). When the user picks an exact `year` (existing control), leave it untouched — the new range selects are separate controls; the backend ANDs whatever is set.
- All new state resets `page` to 1 on change, same as the existing filters.

- [ ] **Step 6: Verify build + manual check, then commit**

Run: `cd ResearchSense/frontend && npm run build` — clean. Manual: filter Publications by a year range + department + conference type; confirm existing search/year/campus filters still behave exactly as before.
```bash
git add ResearchSense/backend/app/routers/publications.py ResearchSense/backend/app/services/publication_service.py ResearchSense/backend/app/repositories/mock/publications.py ResearchSense/backend/tests/test_publication_filters.py ResearchSense/frontend/src/api/publications.ts ResearchSense/frontend/src/pages/Publications.tsx
git commit -m "feat: publications time-period, department, and paper-type filters"
```
