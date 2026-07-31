# ResearchSense — Engagement & Intelligence (Design)

**Date:** 2026-07-31
**Status:** Approved (Approach A — event-log core)

## Goal

Close the faculty-retention gap and add research intelligence: follow/
subscribe with an in-app notification center, a weekly digest (optional
email), per-researcher bibliometrics, a proactive collaboration recommender,
a per-faculty new-paper claim loop, SSE streaming chat, and a RAG evaluation
harness.

**Sequencing:** one phased plan (engagement → intelligence), executed
subagent-driven after the quality-gauntlet plan closes, so the gauntlet
guards this code.

## Decisions made with the user

- **Structure:** one spec, one phased plan.
- **Email:** in-app first; SMTP (stdlib smtplib) activates only when
  `SMTP_HOST/SMTP_PORT/SMTP_USER/SMTP_PASS/SMTP_FROM` env vars are set;
  unset = logged no-op. Zero cost by default.
- **RAG eval:** deterministic retrieval metrics (hit@k, MRR) as the primary
  measure; optional Groq LLM-judge over a sampled subset, manual/offline
  only — never in CI or the gauntlet.

## Architecture: event-log core

One append-only SQLite `events` table is the single source of truth for
"what happened." Notifications, the digest, and claim prompts are pure
derivations over `events` + `follows`. Producers (refresh, approval,
recommender) only append events; they never know about subscribers.
Delivery (bell endpoint, digest page, email) sits at the edges.

Principles this encodes: policy separated from mechanism; pure functions
over immutable facts; state in a few deliberate places; idempotency
everywhere (unique keys make retries safe); graceful degradation (email
absent ≠ failure); single source of truth.

**Numbers first:** 358 researchers / ~1,700 publications today; events
~tens per week; worst-case fan-out (follows × events) ≪ 10⁵ SQLite rows;
recommender scoring O(n²), n=358, at pipeline time only; digest job runs in
seconds; SSE first-token target < 2 s on a warm backend.

## §1 Data model (SQLite, additive)

```sql
CREATE TABLE IF NOT EXISTS follows (
    orcid_id   TEXT NOT NULL,
    kind       TEXT NOT NULL,          -- 'researcher' | 'topic' | 'department'
    target     TEXT NOT NULL,          -- researcher_id / topic name / dept name
    created_at TEXT NOT NULL,
    PRIMARY KEY (orcid_id, kind, target)
);
CREATE TABLE IF NOT EXISTS events (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    kind        TEXT NOT NULL,         -- see catalogue below
    subject_id  INTEGER,               -- researcher the event is about (nullable)
    payload     TEXT NOT NULL,         -- JSON
    created_at  TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS notifications (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    orcid_id   TEXT NOT NULL,
    event_id   INTEGER NOT NULL,
    read       INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    UNIQUE (orcid_id, event_id)        -- fan-out idempotency
);
CREATE TABLE IF NOT EXISTS claim_decisions (
    orcid_id        TEXT NOT NULL,
    publication_key TEXT NOT NULL,     -- normalized DOI or title+year key
    decision        TEXT NOT NULL,     -- 'accepted' | 'declined'
    created_at      TEXT NOT NULL,
    PRIMARY KEY (orcid_id, publication_key)
);
```

**Event catalogue** (`kind` values): `publication_added` (payload: pub id,
title, topics, department, authors), `submission_approved`,
`submission_rejected` (payload includes note), `claim_candidates` (payload:
list of candidate publication keys + titles), `recommendations_changed`
(payload: new top-5 ids). Events are append-only; nothing updates or
deletes them.

**Fan-out** is one pure function:
`fanout(events, follows, accounts) -> list[(orcid_id, event_id)]` —
a follower of a researcher gets that researcher's `publication_added`;
topic/department followers match on payload topics/department; the
submitter (subject) gets `submission_*` and `claim_candidates` and
`recommendations_changed` regardless of follows. Inserted with
`INSERT OR IGNORE` (unique key) after each refresh and after each
approval/rejection.

## §2 Follow + notification center

- API: `POST /api/follows` {kind, target} / `DELETE /api/follows` (faculty
  auth); `GET /api/follows/mine`; `GET /api/notifications` → rows (event
  kind, human-readable text, created_at, read) + unread count;
  `POST /api/notifications/read` {ids} marks read.
- UI: follow/unfollow button on researcher profile, topic page, and
  department filter header; bell icon with unread badge in the header
  (visible when signed in); dropdown or panel listing notifications,
  mark-all-read.
- Notification text is rendered from the event payload by one pure
  formatter per event kind (table-driven, not branching sprawl).

## §3 Weekly digest + optional email

- `build_digest(events, follows, researcher, window_days=7) -> Digest`
  (pure): sections — new papers in your followed areas/people, your
  submissions' status changes, your pending claim candidates, your current
  top recommendation, your metrics delta (uses §4 values embedded in
  events/researcher record).
- Portal page "Your weekly digest" renders the same model on demand.
- Email: after the existing weekly refresh, for each active account build
  the digest; when SMTP env vars are configured, send as plain-text email
  via smtplib with a 10 s timeout; per-user failures are logged and
  skipped. When unconfigured, log `digest email skipped (no SMTP config)`
  once per run. Config read once at send time — fail fast on partial
  config (some-but-not-all SMTP vars set → loud error, no sends).

## §4 Per-researcher bibliometrics

Pipeline-time pure functions over a researcher's publications:
- `h_index(citations: list[int]) -> int`
- `i10(citations: list[int]) -> int`
- `citations_by_year(pubs) -> list[{year, citations}]` (publication-year
  attribution, last 5 years)
- `citation_velocity(pubs, now_year) -> int` — total citations of papers
  published in the last 2 years.
Stored on the researcher record (`bibliometrics` object). Public profile
shows a metrics row (h-index, i10, citations, velocity); portal dashboard
shows "Your impact" with the per-year series. Zero derivation at request
time.

## §5 Proactive collaboration recommender

Pipeline-time:
- Build co-authorship graph from publications (edge weight = co-pub count).
- Candidate pairs = same-department or shared-topic or graph-distance-2
  researchers without an existing edge.
- Score = Adamic–Adar over mutual co-authors + Jaccard topic overlap +
  0.25 same-campus bonus + 0.25 cross-department-shared-topic bonus
  (interdisciplinary nudge). Weights are named constants in one table.
- Top-5 per researcher stored as `recommended_collaborators`:
  [{researcher_id, name, score, reasons: ["2 mutual co-authors",
  "both publish in Deep Learning"]}] — reasons generated from the same
  scoring components (explainable by construction).
- When a refresh changes someone's top-5 set, append one
  `recommendations_changed` event for them.
- Portal dashboard: "People you could collaborate with" card, top-5 with
  reasons, linking to profiles. Public reactive collaborators endpoint is
  unchanged.

## §6 New-paper claim loop

- During refresh, author matches that FAIL auto-link (fuzzy name match but
  no field-guard pass, or >1 ambiguous roster candidate) are no longer
  dropped: they become per-researcher claim candidates, minus any
  publication_key already in `claim_decisions` for that researcher. One
  `claim_candidates` event per researcher per refresh (payload lists the
  candidates).
- API (faculty auth): `GET /api/claims/mine` → pending candidates with
  title/venue/year/DOI; `POST /api/claims/{key}/accept` → sets the
  publication's matching author row `researcher_id`, bumps
  publication/citation counts, appends the fact-card chunk to the live
  index, records decision; `POST /api/claims/{key}/decline` → records
  decision only. Both idempotent (decision table PK; accept on an
  already-linked paper is a no-op).
- Portal: "We found N papers that might be yours" card with per-paper
  Accept / Not mine.

## §7 SSE streaming chat

- `POST /api/chat/stream` returns `text/event-stream`
  (`StreamingResponse`): events `token` (delta text), `sources` (the
  source-chip payload, sent once), `done`, `error` (message). Wired to
  Groq's streaming mode in the generator service; retrieval is unchanged.
- Frontend chat switches to the stream endpoint, appending tokens to the
  in-progress message; on `error` or connection failure it falls back to
  the existing non-streaming POST (which remains for compatibility and the
  eval harness).
- Target: first token < 2 s warm; the UI shows the existing typing
  indicator until the first token.

## §8 RAG evaluation harness

- `backend/eval/golden.json`: ~30 questions, each
  {question, expected_labels: [chunk-label substrings], expected_kind}.
  Written against the current corpus; regenerating data may require
  updating the golden set (documented).
- `python -m scripts.rag_eval`: runs the retriever for each question,
  reports hit@1, hit@5, MRR overall and per expected_kind; writes
  `eval/results-<date>.json`; exits non-zero if hit@5 falls below a floor
  recorded in the file header (default 0.7) — a regression tripwire for
  manual runs.
- `python -m scripts.rag_eval --judge 10`: additionally samples 10
  questions end-to-end (generation included) and has Groq grade
  groundedness/relevance 1–5 with the rubric in the prompt; prints mean
  scores; never runs in CI/gauntlet (network + nondeterminism).
- docs/QA.md gains a "RAG evaluation" section (when to run, how to read
  results, updating the golden set after data refreshes).

## Error handling

- Fan-out and digest jobs never abort the refresh: failures are logged per
  stage; events remain the durable record so a rerun re-derives.
- SMTP: partial config fails fast and loud; full config with send failure
  logs and skips that user; no config is a silent-by-design no-op (logged
  once).
- SSE: generator exceptions emit an `error` event then close; the client
  falls back to non-streaming.
- Claim accept on a publication that disappeared after a data refresh →
  404 with a clear message; the decision is still recorded so it never
  reappears.

## Testing

- Pure units: h_index/i10/velocity, Adamic–Adar + reasons, fanout,
  build_digest, claim-candidate filtering + idempotent decisions, digest
  SMTP config validation.
- API: follows/notifications/claims via TestClient + tmp SQLite (existing
  patterns); SSE via TestClient streaming.
- BDD (post-gauntlet): "follow a researcher → new paper → notification"
  and "claim candidate → accept → paper on profile" scenarios.
- RAG eval harness validates itself against a 3-question fixture corpus in
  tests (no model download in CI: retriever monkeypatched).
