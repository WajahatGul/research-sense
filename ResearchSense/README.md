# ResearchSense

A research information system for **Bahria University** — researcher profiles,
publications, research areas, funded projects, a collaboration finder, an
analytics dashboard, a faculty portal, and a grounded AI research assistant.
Covers the computing faculty of all four teaching campuses: Islamabad (E-8),
Islamabad (H-11), Karachi, and Lahore. Built as a Final Year Project; zero
running cost end to end.

## Features

- **Real data pipeline** — 225 researchers scraped from the university faculty
  directory (names, designations, emails, expertise, education) and 675+ real
  publications matched from OpenAlex with a field-overlap guard against
  same-name authors. Sample records (projects/funding) are flagged `sample`.
- **Grounded RAG chatbot** — answers only from indexed data and the full text
  of downloaded faculty papers. A retrieval confidence gate plus a strict
  context-only prompt (Groq free tier, Llama 3.3 70B, temperature 0) means it
  refuses instead of inventing. Conversation memory supports follow-ups.
- **Chat with papers** — open-access PDFs are downloaded per researcher from
  OpenAlex/Semantic Scholar, chunked, and embedded locally (fastembed
  all-MiniLM-L6-v2, CPU, free).
- **Analytics** — publications per year by campus, citation growth, top venues,
  campus totals, and cross-campus collaboration, derived live from the data.
- **Faculty portal** — researchers claim their profile with their ORCID iD and
  a password (PBKDF2 + JWT), then upload their own papers; uploads are indexed
  into the assistant immediately. Claimed profiles show a badge.
- **Admin** — accounts overview, activate/deactivate, and manual data refresh.
  A background task also refreshes publications and the index every 7 days.

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
python -m scripts.fetch_publications    # real publications from OpenAlex
python -m scripts.download_papers       # open-access PDFs per researcher
python -m scripts.build_index           # RAG chunks + embeddings
```

The admin "Refresh data now" button (and the weekly background job) re-runs the
publications fetch and the index build automatically.
