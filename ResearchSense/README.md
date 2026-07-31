# ResearchSense

A research information system for **Bahria University** — researcher profiles,
publications, research areas, funded projects, a collaboration finder, an
analytics dashboard, a faculty portal, and a grounded AI research assistant.
Covers all 22 academic departments across the four teaching campuses:
Islamabad (E-8), Islamabad (H-11), Karachi, and Lahore. Built as a Final Year
Project; zero running cost end to end.

## Features

- **Real data pipeline** — 708 faculty scraped from the university faculty
  directory across all 22 departments and 4 campuses (names, designations,
  emails, expertise, education); 358 sampled into the app, capped at
  `FACULTY_PER_DEPT` (12) per campus+department so no single department
  dominates the corpus, preferring faculty with listed research areas and
  senior designations. 1,667 publications matched and deduplicated (by DOI,
  then title+year) from OpenAlex plus Semantic Scholar and Crossref
  supplementary passes, with a field-overlap guard against same-name authors —
  887 flagged international, 252 researchers have linked publications, 357
  have derived research areas, across 740 topics. Sample records
  (projects/funding) are flagged `sample`.
- **Grounded RAG chatbot** — answers only from indexed data and the full text
  of downloaded faculty papers. A retrieval confidence gate plus a strict
  context-only prompt (Groq free tier, Llama 3.3 70B, temperature 0) means it
  refuses instead of inventing. Conversation memory supports follow-ups, and
  fact-card chunks cover derived research areas and international
  collaborations so the assistant can answer "who collaborates
  internationally"-style questions from retrieval.
- **Chat with papers** — open-access PDFs are downloaded per researcher from
  OpenAlex/Semantic Scholar, chunked, and embedded locally (fastembed
  all-MiniLM-L6-v2, CPU, free). The weekly refresh only adds newly available
  PDFs and keeps existing ones, so coverage grows over time rather than being
  re-downloaded from scratch.
- **Analytics** — publications per year by campus, citation growth, top venues,
  campus totals, department totals, an international-vs-domestic split, and
  cross-campus collaboration, derived live from the data.
- **Publications page** — year-range, department, and paper-type filters.
- **Faculty portal** — researchers claim their profile with their ORCID iD and
  a password (PBKDF2 + JWT), then submit or upload their own papers. Uploaded
  papers are indexed into the assistant immediately; portal-submitted
  publications now require admin approval before appearing publicly (staged
  embeddings make approval instant once approved), while scraped/OpenAlex
  publications remain auto-published. Claimed profiles show a badge.
- **Admin** — accounts overview, activate/deactivate, pending-submission
  approval queue, and manual data refresh. A background task also refreshes
  publications and the index every 7 days.

## Architecture

```
Frontend (React + TS)  ──HTTP──►  FastAPI
  api/ (typed clients)              routers/   thin HTTP layer
  types/ (mirror schemas)           services/  business logic (incl. rag/, auth)
  components/ features/ pages/      repositories/  JSON corpus + SQLite accounts
                                    schemas/   Pydantic contract
                                    data/      seed JSON + RAG index + SQLite
```

- Components never call `fetch` directly — only `src/api/*`.
- Routers hold no logic; repositories are the only code touching data sources.
- Read-only research corpus lives in JSON; mutable data (accounts, uploads,
  refresh log) lives in SQLite. Every source file stays under ~350 lines.
- Frontend typography and spacing use fluid `clamp()` scales rather than fixed
  breakpoints.

## Run it

**Backend** (Python 3.13):

```bash
cd backend
python -m venv .venv
.venv/Scripts/activate        # Windows;  source .venv/bin/activate on macOS/Linux
pip install -r requirements.txt
python -m uvicorn app.main:app --reload --port 8000
```

Create `backend/.env` with:

```
GROQ_API_KEY=...      # free key from console.groq.com (chatbot LLM)
ADMIN_USERNAME=admin  # admin portal login
ADMIN_PASSWORD=...    # required for admin login
```

API docs: http://127.0.0.1:8000/docs

**Frontend** (Node 18+):

```bash
cd frontend
npm install
npm run dev                   # http://127.0.0.1:5173
```

The Vite dev server proxies `/api` to the backend, so no CORS setup is needed.

## Data pipeline (run in order after a fresh clone)

```bash
cd backend
python -m playwright install chromium   # one time
python -m scripts.scrape_bahria         # faculty directory -> scraped_faculty.json
python -m scripts.build_seed            # researchers/topics/projects JSON
python -m scripts.fetch_publications    # OpenAlex + Semantic Scholar + Crossref, deduped
python -m scripts.download_papers       # open-access PDFs per researcher
python -m scripts.build_index           # RAG chunks + embeddings
```

The admin "Refresh data now" button (and the weekly background job) re-runs the
publications fetch and the index build automatically.
