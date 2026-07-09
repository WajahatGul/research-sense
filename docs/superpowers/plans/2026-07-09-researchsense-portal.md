# ResearchSense Portal Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a professional research information portal for Bahria University Islamabad (E-8) — React+TS frontend and FastAPI backend serving real scraped Bahria faculty data from mock JSON, architected for a drop-in DB swap later.

**Architecture:** Backend follows router → service → repository → data source, with the data source hidden behind a repository interface (mock JSON now, SQL later). Frontend consumes data only through a typed API client layer; components never fetch directly. Pydantic schemas and mirrored TS types form the contract.

**Tech Stack:** Frontend — Vite, React 18, TypeScript, React Router, TanStack Query, CSS Modules. Backend — FastAPI, Pydantic v2, Uvicorn, Playwright (scrape script only).

## Global Constraints

- Every source file ≤ 350 lines; one responsibility per file.
- Frontend components MUST NOT call `fetch`/`axios` directly — only `src/api/*` clients.
- Backend routers hold no business logic; repositories are the only code that touches the data source.
- Code lives under a new `ResearchSense/` folder; the noisy FYP root stays untouched.
- Data model mirrors `researchsense_erd_v2`. Every record carries a `source` field: `"scraped"` or `"sample"`.
- Bahria branding (navy/gold), NU/Pure layout structure.

---

## Phase A — Backend foundation

### Task A1: Project scaffold + git
**Files:** Create `ResearchSense/backend/app/__init__.py`, `ResearchSense/backend/requirements.txt`, `ResearchSense/.gitignore`, `ResearchSense/README.md`
- [ ] Init git repo at `ResearchSense/`; add `.gitignore` (node_modules, __pycache__, .venv, dist, .playwright-mcp).
- [ ] `requirements.txt`: fastapi, uvicorn[standard], pydantic, playwright.
- [ ] Commit: "chore: scaffold ResearchSense repo".

### Task A2: Pydantic schemas (the contract)
**Files:** Create `backend/app/schemas/{researcher,publication,topic,project,common}.py`
**Produces:** `Researcher`, `ResearcherDetail`, `Publication`, `Topic`, `Project`, `Funding`, `Stats`, `Paginated[T]` models.
- [ ] One file per resource group, each model < 350 lines. Fields match ERD (researcher_id, full_name, department, designation, orcid_id, profile_bio, topics[], publications[]; publication with title/year/journal/authors/topics; project with funding).
- [ ] `common.py`: `Paginated` generic + `Stats` (researchers, publications, projects, topics counts).
- [ ] Commit.

### Task A3: Repository interface + mock implementation
**Files:** Create `backend/app/repositories/base.py`, `backend/app/repositories/mock/{researchers,publications,topics,projects}.py`, `backend/app/repositories/loader.py`
**Interfaces:**
- Produces: abstract `ResearcherRepository`, `PublicationRepository`, `TopicRepository`, `ProjectRepository` with methods `list(filters)`, `get(id)`, plus `StatsRepository.get_stats()`.
- Mock impls read JSON via `loader.load(name)` (cached). SQL impls slot in later behind same interface.
- [ ] Write interface (ABC) then mock impls that filter/paginate in memory.
- [ ] Commit.

### Task A4: Services + routers + app factory
**Files:** Create `backend/app/services/*.py`, `backend/app/routers/*.py`, `backend/app/core/{config,app.py}`, `backend/app/main.py`
**Produces routes:** `GET /api/stats`, `/api/researchers`(+filters, pagination), `/api/researchers/{id}`, `/api/publications`, `/api/topics`, `/api/projects`, `/api/chat` (mock echo/RAG-shell).
- [ ] Services depend on repository interfaces (constructor injection via `core/deps.py`).
- [ ] Routers thin; CORS enabled for the Vite dev origin.
- [ ] Smoke test: `uvicorn app.main:app` → `curl /api/stats` returns counts.
- [ ] Commit.

## Phase B — Real data

### Task B1: Scrape script
**Files:** Create `backend/scripts/scrape_bahria.py`, output to `backend/app/data/*.json`
- [ ] Playwright: load E-8 CS faculty roster (bahria.edu.pk PageTemplate4) + each `Home/FacultyDetails?facultyId=`; extract name, designation, bio, dept.
- [ ] Normalize to `researchers.json`; generate `topics.json`, `publications.json`, `projects.json`, `funding.json` with realistic sample values linked to researchers, each flagged `source:"sample"`.
- [ ] Run script; verify ≥40 researchers loaded. Commit data + script.

## Phase C — Frontend

### Task C1: Vite scaffold + theme + layout
**Files:** `frontend/` (Vite react-ts), `src/styles/theme.css`, `src/layout/{Header,Footer,Layout}.tsx`, router in `src/App.tsx`, `src/lib/queryClient.ts`
- [ ] Bahria theme tokens (navy #0a2a5e, gold #c9a227), global reset, typography.
- [ ] Header with nav (Home, Researchers, Publications, Topics, Projects, Collaboration, Ask), Footer.
- [ ] Commit.

### Task C2: Types + API clients
**Files:** `src/types/*.ts` (mirror Pydantic), `src/api/{client,researchers,publications,topics,projects,stats,chat}.ts`
- [ ] `client.ts` base fetch wrapper (baseURL from env). One typed function per endpoint.
- [ ] Commit.

### Task C3: Home page
**Files:** `src/pages/Home.tsx`, `src/features/home/{Hero,StatsRow,FeaturedResearchers,DepartmentGrid,ResearchAreas}.tsx`, `src/components/{StatCard,ResearcherCard,SearchBar}.tsx`
- [ ] Pure-style hero + search, animated stat counters from `/api/stats`, featured researchers, dept grid, research-areas block.
- [ ] Verify against running backend. Commit.

### Task C4: Researchers directory + profile
**Files:** `src/pages/Researchers.tsx`, `src/pages/ResearcherProfile.tsx`, `src/features/researchers/{FilterBar,ResearcherList}.tsx`
- [ ] Filterable list (dept/designation/topic) with TanStack Query; profile page with bio, publications, topics, collaboration suggestions.
- [ ] Commit.

### Task C5: Publications + Topics + Projects
**Files:** `src/pages/{Publications,Topics,Projects}.tsx` + feature components
- [ ] Publications searchable list w/ year/topic/author filters; topics browse; projects+funding list.
- [ ] Commit.

### Task C6: Collaboration + Chatbot UI
**Files:** `src/pages/{Collaboration,Ask}.tsx`, `src/features/collaboration/NetworkView.tsx`, `src/features/chat/ChatPanel.tsx`
- [ ] Collaboration recommendations view; chat shell posting to `/api/chat` (mock answers).
- [ ] Commit.

### Task C7: Polish + run docs
**Files:** `ResearchSense/README.md`, root run scripts
- [ ] Document how to run backend + frontend. Responsive check. Final commit.

## Self-Review

- Spec coverage: Home ✓(C3), Researchers/profile ✓(C4), Publications/Topics/Projects ✓(C5), Collaboration+Chatbot ✓(C6), FastAPI mock/repository seam ✓(A3–A4), scraped data ✓(B1), typed API layer ✓(C2), folder structure & ≤350 lines ✓(constraints).
- No placeholders in structure; each task has concrete files and deliverables.
- Type consistency: schemas (A2) → TS types (C2) mirror same field names.
