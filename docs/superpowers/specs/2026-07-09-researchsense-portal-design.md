# ResearchSense — Phase 1 Design (UI + FastAPI mock)

**Date:** 2026-07-09
**Status:** Approved
**Scope:** Phase 1 — full UI for a research information portal + FastAPI backend serving mock JSON (real scraped Bahria data). No real DB, auth, or live NLP/RAG yet.

## 1. Goal

A professional research information portal for **Bahria University Islamabad (E-8 campus)**,
modeled on the Elsevier Pure layout at research.nu.edu.kz but with Bahria branding.
Built with **React + TypeScript** (frontend) and **FastAPI** (backend serving mock JSON),
architected so that swapping mock data for a real database is a drop-in change at the
repository layer only.

Primary reference for feature/layout ideas: https://research.nu.edu.kz/en/ (Elsevier Pure).
Not a pixel copy — same structure, Bahria identity.

## 2. Architecture

```
FastAPI:  router → service → repository → data source
                                   ↑
                    MockRepository (JSON now) ── swap ──► SqlRepository (later)
```

- **Routers** are thin: parse request, call service, return schema. No business logic.
- **Services** hold business logic and orchestration.
- **Repositories** hide the data source behind an interface
  (`ResearcherRepository`, `PublicationRepository`, etc.). Mock implementation reads JSON;
  a future SQL implementation swaps in without touching routers/services.
- **Pydantic schemas** are the API contract.
- **Frontend** talks only to typed API-client functions (`src/api/*`); components never
  call `fetch` directly. TypeScript interfaces in `src/types/*` mirror the Pydantic schemas.

Principles applied: Separation of Concerns, Dependency Inversion (repository interface),
High Cohesion / Loose Coupling (per-resource modules), Abstraction/Encapsulation
(data source hidden behind repository).

## 3. Data pipeline (one-time, offline)

`backend/scripts/scrape_bahria.py` uses Playwright to pull the E-8 faculty roster and
individual `Home/FacultyDetails?facultyId=...` detail pages from bahria.edu.pk, then
normalizes the results into JSON files that match the project ERD:

- `researchers.json`, `publications.json`, `authors.json`, `topics.json`,
  `projects.json`, `funding.json`, and the join/relationship files as needed.

Data Bahria does not publish (publication lists, topics, funding amounts) is filled with
realistic derived/sample values, flagged with a `source` field (e.g. `"sample"` vs
`"scraped"`) so the portal looks complete and the provenance stays honest. Seed JSON is
committed under `backend/app/data/`.

## 4. Pages (Phase 1 scope — all sections)

- **Home** — Bahria hero + search bar, live stat counters (Researchers, Publications,
  Projects, Topics), featured researchers, department grid, research-areas block, footer.
- **Researchers** — filterable directory (department, designation, topic) →
  **Profile page** (bio, designation, department, publications, topics, collaboration
  suggestions).
- **Publications** — searchable list; filters by year, topic, author.
- **Topics & Projects/Funding** — topic browse pages; projects list with funding info.
- **Collaboration + Chatbot** — collaboration network/recommendations view + a
  RAG-chatbot chat UI shell (returns mock answers in Phase 1).

## 5. Folder structure

```
ResearchSense/
├─ frontend/  (Vite + React + TS)
│  └─ src/
│     ├─ api/         # typed API clients, one file per resource
│     ├─ types/       # TS interfaces mirroring Pydantic schemas
│     ├─ components/  # reusable UI (Header, StatCard, ResearcherCard, …)
│     ├─ features/    # per-page feature folders
│     ├─ pages/       # route-level components
│     ├─ layout/      # Header, Footer, page shell
│     ├─ hooks/       # shared hooks
│     ├─ lib/         # query client, helpers
│     └─ styles/      # theme tokens, global css
├─ backend/   (FastAPI)
│  ├─ app/
│  │  ├─ routers/       # thin HTTP endpoints per resource
│  │  ├─ services/      # business logic per resource
│  │  ├─ repositories/  # data-access interface + mock impl
│  │  ├─ schemas/       # Pydantic models
│  │  ├─ core/          # config, app factory, CORS
│  │  └─ data/          # seed JSON
│  └─ scripts/          # scrape_bahria.py
└─ docs/
```

Every file kept to **250–350 lines max**; one responsibility per file/folder.

## 6. Stack

- **Frontend:** Vite, React 18, TypeScript, React Router, TanStack Query (data caching),
  CSS modules (no heavy UI kit — keeps the design distinctive and Bahria-branded).
- **Backend:** FastAPI, Pydantic v2, Uvicorn. No database in Phase 1.

## 7. Out of scope for Phase 1 (clean extension points, not rework)

- Real authentication / user accounts.
- Live NLP pipeline and real RAG chatbot (chatbot returns mock answers).
- Real relational database (repository interface is the seam for this).
- Real publication ingestion (DOI/Crossref, PDF upload).

## 8. Success criteria

- All Phase 1 pages render with real Bahria E-8 faculty data.
- Frontend consumes data exclusively through the typed API layer hitting FastAPI.
- Backend data access is isolated behind repository interfaces (mock swappable for DB).
- No source file exceeds ~350 lines; clear one-purpose-per-file organization.
- Portal looks professional and production-credible for customer demos.
