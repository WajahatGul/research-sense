# ResearchSense Phase 3 — Papers at Scale, Analytics, Faculty Accounts

**Date:** 2026-07-10
**Status:** Approved (user-specified feature set and constraints)
**Constraints:** zero running cost, production-grade behavior, KISS/DRY/YAGNI,
files ≤ 350 lines, existing router → service → repository seams.

## 1. Chat with any paper (corpus at scale)

`scripts/download_papers.py` generalizes from one professor to every researcher
with indexed publications: resolve each OpenAlex author (Bahria-affiliated),
download up to 5 open-access PDFs each (most cited first; existing files always
kept). `papers/manifest.json` entries gain `researcher_id` and `author_name`,
so index chunks and chat source chips attribute each paper to its author.
`build_index.py` reads attribution from the manifest.

## 2. Analytics dashboard

Backend: `GET /api/analytics` computes aggregates from the existing JSON data
in one service — publications per year (per campus), citations per year, top
venues, per-campus totals, and cross-campus co-authorship counts. No new
storage; pure derivation (DRY: one source of truth).
Frontend: `/analytics` page rendering the aggregates as charts.

## 3. Faculty accounts, profile claiming, paper upload, auto-refresh

- **Storage:** mutable data (accounts, uploads, refresh log) lives in SQLite
  (`app/data/researchsense.db`, stdlib sqlite3, ACID). The scraped research
  corpus stays read-only JSON. Different lifecycles, different stores.
- **Claiming:** a researcher claims their profile with their ORCID iD
  (validated format) + a password. One account per researcher and per ORCID.
  Claimed profiles show a "Claimed" badge. Passwords: PBKDF2-HMAC-SHA256
  (stdlib), per-user salt. Sessions: signed JWT (PyJWT), 7-day expiry.
- **Admin:** single admin account from `.env` (`ADMIN_USERNAME`,
  `ADMIN_PASSWORD`); can list claims, deactivate accounts, and trigger a data
  refresh manually.
- **Paper upload:** logged-in faculty upload their own PDF (≤ 15 MB, magic-byte
  checked). The file is chunked, embedded, and appended to the live RAG index
  without a full rebuild; the chatbot can answer from it immediately.
- **Auto-refresh:** a background task in the FastAPI lifespan checks daily; if
  the last refresh is older than 7 days it re-runs the OpenAlex publication
  fetch and rebuilds the index, recording the run in SQLite. Fail loud: errors
  are logged, never swallowed silently. (No external scheduler needed; a
  GitHub Actions cron can replace it in cloud deployment.)

## Out of scope (YAGNI)

ORCID OAuth, email verification, password reset flows, rate limiting,
multi-admin roles, upload moderation queues.
