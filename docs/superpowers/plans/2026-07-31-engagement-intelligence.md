# Engagement & Intelligence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Faculty retention + research intelligence per `docs/superpowers/specs/2026-07-31-engagement-intelligence-design.md`: event-log core, follow/notifications, weekly digest with optional SMTP, per-researcher bibliometrics, proactive recommender, new-paper claim loop, SSE streaming chat, RAG eval harness.

**Architecture:** Append-only `events` in SQLite is the single source of truth; notifications/digest/claims are pure derivations; delivery at the edges. All heavy computation (bibliometrics, recommender, claim candidates) happens at pipeline/refresh time; request handlers read.

**Tech Stack:** FastAPI + stdlib sqlite3/smtplib, fastembed retriever (unchanged), Groq streaming; React + @tanstack/react-query; pytest (+ the gauntlet's gates, which must stay green after every task).

## Global Constraints

- Backend from `ResearchSense/backend/` with `.venv/Scripts/python`; frontend from `ResearchSense/frontend/`. Windows Git Bash.
- The quality gauntlet is live: after EVERY task run `python -m scripts.gauntlet --backend-only` (backend tasks) or the full gauntlet (frontend tasks) — all gates green before commit. Coverage floor may need no change (new code ships with tests); never lower it.
- No gate/test touches live `app/data/*` or the network; tmp_path + inline fixtures only (existing suite patterns).
- Events are append-only; producers never write notifications directly; fan-out idempotency via `UNIQUE(orcid_id, event_id)` + `INSERT OR IGNORE`.
- SMTP env vars: `SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS, SMTP_FROM` — all-or-nothing: partial config raises `ValueError` loudly; none = logged no-op; send timeout 10 s.
- Event kinds (exact strings): `publication_added`, `submission_approved`, `submission_rejected`, `claim_candidates`, `recommendations_changed`.
- Files ≤ ~350 lines; thin routers; repositories/services own logic; do not stage/commit `app/data/*.json`, `*.npz`, `papers/`, or `eval/results-*.json`.
- SSE event shape on `POST /api/chat/stream`: SSE `data:` lines each carrying JSON `{"type": "sources"|"token"|"done"|"error", ...}`; `sources` sent once before tokens; target first token < 2 s warm.

---

### Task 1: Engagement store — follows / events / notifications / claim_decisions

**Files:**
- Modify: `ResearchSense/backend/app/repositories/accounts.py` (`_SCHEMA` + methods)
- Create: `ResearchSense/backend/tests/test_engagement_store.py`

**Interfaces:**
- Produces (exact signatures; Tasks 2, 3, 6, 7 call these):
  - `add_follow(orcid_id: str, kind: str, target: str) -> None` (idempotent), `remove_follow(orcid_id, kind, target) -> None`, `follows_for(orcid_id) -> list[dict]`, `all_follows() -> list[dict]`
  - `append_event(kind: str, subject_id: int | None, payload: dict) -> int`, `events_since(iso_ts: str) -> list[dict]` (payload parsed to dict)
  - `insert_notifications(pairs: list[tuple[str, int]]) -> int` (INSERT OR IGNORE; returns inserted count), `notifications_for(orcid_id) -> list[dict]` (joined with events, newest first), `unread_count(orcid_id) -> int`, `mark_read(orcid_id, ids: list[int]) -> None`
  - `record_claim_decision(orcid_id: str, publication_key: str, decision: str) -> None` (INSERT OR REPLACE), `claim_decisions_for(orcid_id) -> set[str]`

- [ ] **Step 1: Write the failing tests**

`tests/test_engagement_store.py`:
```python
import pytest

import app.repositories.accounts as accounts_mod
from app.repositories.accounts import AccountStore


@pytest.fixture()
def store(tmp_path, monkeypatch):
    monkeypatch.setattr(accounts_mod, "DB_PATH", tmp_path / "t.db")
    AccountStore._instance = None
    yield AccountStore.instance()
    AccountStore._instance = None


def test_follow_roundtrip_and_idempotency(store):
    store.add_follow("0000-1", "researcher", "42")
    store.add_follow("0000-1", "researcher", "42")  # duplicate is a no-op
    assert [f["target"] for f in store.follows_for("0000-1")] == ["42"]
    store.remove_follow("0000-1", "researcher", "42")
    assert store.follows_for("0000-1") == []


def test_event_append_and_read(store):
    eid = store.append_event("publication_added", 7, {"title": "T"})
    rows = store.events_since("2000-01-01T00:00:00")
    assert rows[0]["id"] == eid and rows[0]["payload"]["title"] == "T"
    assert rows[0]["kind"] == "publication_added"


def test_notification_fanout_is_idempotent(store):
    eid = store.append_event("publication_added", 7, {})
    assert store.insert_notifications([("0000-1", eid), ("0000-1", eid)]) == 1
    assert store.unread_count("0000-1") == 1
    rows = store.notifications_for("0000-1")
    store.mark_read("0000-1", [rows[0]["id"]])
    assert store.unread_count("0000-1") == 0


def test_claim_decisions_never_reask(store):
    store.record_claim_decision("0000-1", "doi:10.1/x", "declined")
    store.record_claim_decision("0000-1", "doi:10.1/x", "accepted")  # replace ok
    assert store.claim_decisions_for("0000-1") == {"doi:10.1/x"}
```

- [ ] **Step 2: Run to verify failure**

Run: `cd ResearchSense/backend && .venv/Scripts/python -m pytest tests/test_engagement_store.py -v` → FAIL (methods missing).

- [ ] **Step 3: Implement**

Append to `_SCHEMA` in accounts.py:
```sql
CREATE TABLE IF NOT EXISTS follows (
    orcid_id   TEXT NOT NULL,
    kind       TEXT NOT NULL,
    target     TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (orcid_id, kind, target)
);
CREATE TABLE IF NOT EXISTS events (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    kind       TEXT NOT NULL,
    subject_id INTEGER,
    payload    TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS notifications (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    orcid_id   TEXT NOT NULL,
    event_id   INTEGER NOT NULL,
    read       INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    UNIQUE (orcid_id, event_id)
);
CREATE TABLE IF NOT EXISTS claim_decisions (
    orcid_id        TEXT NOT NULL,
    publication_key TEXT NOT NULL,
    decision        TEXT NOT NULL,
    created_at      TEXT NOT NULL,
    PRIMARY KEY (orcid_id, publication_key)
);
```
Methods on `AccountStore` (same style as existing ones — one `with self._connect()` per operation; `import json` is already available at module top or add it):
```python
    # --- engagement: follows / events / notifications / claims ---
    def add_follow(self, orcid_id: str, kind: str, target: str) -> None:
        with self._connect() as con:
            con.execute(
                "INSERT OR IGNORE INTO follows (orcid_id, kind, target,"
                " created_at) VALUES (?, ?, ?, ?)",
                (orcid_id, kind, target, _now()))

    def remove_follow(self, orcid_id: str, kind: str, target: str) -> None:
        with self._connect() as con:
            con.execute(
                "DELETE FROM follows WHERE orcid_id = ? AND kind = ?"
                " AND target = ?", (orcid_id, kind, target))

    def follows_for(self, orcid_id: str) -> list[dict]:
        with self._connect() as con:
            rows = con.execute(
                "SELECT kind, target, created_at FROM follows"
                " WHERE orcid_id = ? ORDER BY created_at", (orcid_id,)).fetchall()
        return [dict(r) for r in rows]

    def all_follows(self) -> list[dict]:
        with self._connect() as con:
            rows = con.execute(
                "SELECT orcid_id, kind, target FROM follows").fetchall()
        return [dict(r) for r in rows]

    def append_event(self, kind: str, subject_id: int | None,
                     payload: dict) -> int:
        import json as _json
        with self._connect() as con:
            cur = con.execute(
                "INSERT INTO events (kind, subject_id, payload, created_at)"
                " VALUES (?, ?, ?, ?)",
                (kind, subject_id, _json.dumps(payload, ensure_ascii=False),
                 _now()))
            return int(cur.lastrowid)

    def events_since(self, iso_ts: str) -> list[dict]:
        import json as _json
        with self._connect() as con:
            rows = con.execute(
                "SELECT * FROM events WHERE created_at >= ? ORDER BY id",
                (iso_ts,)).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            d["payload"] = _json.loads(d["payload"])
            out.append(d)
        return out

    def insert_notifications(self, pairs: list[tuple[str, int]]) -> int:
        inserted = 0
        with self._connect() as con:
            for orcid_id, event_id in pairs:
                cur = con.execute(
                    "INSERT OR IGNORE INTO notifications (orcid_id, event_id,"
                    " created_at) VALUES (?, ?, ?)",
                    (orcid_id, event_id, _now()))
                inserted += cur.rowcount
        return inserted

    def notifications_for(self, orcid_id: str) -> list[dict]:
        import json as _json
        with self._connect() as con:
            rows = con.execute(
                "SELECT n.id, n.read, n.created_at, e.kind, e.subject_id,"
                " e.payload FROM notifications n JOIN events e"
                " ON e.id = n.event_id WHERE n.orcid_id = ?"
                " ORDER BY n.id DESC LIMIT 50", (orcid_id,)).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            d["payload"] = _json.loads(d["payload"])
            out.append(d)
        return out

    def unread_count(self, orcid_id: str) -> int:
        with self._connect() as con:
            row = con.execute(
                "SELECT COUNT(*) c FROM notifications WHERE orcid_id = ?"
                " AND read = 0", (orcid_id,)).fetchone()
        return int(row["c"])

    def mark_read(self, orcid_id: str, ids: list[int]) -> None:
        with self._connect() as con:
            con.executemany(
                "UPDATE notifications SET read = 1 WHERE orcid_id = ?"
                " AND id = ?", [(orcid_id, i) for i in ids])

    def record_claim_decision(self, orcid_id: str, publication_key: str,
                              decision: str) -> None:
        with self._connect() as con:
            con.execute(
                "INSERT OR REPLACE INTO claim_decisions (orcid_id,"
                " publication_key, decision, created_at) VALUES (?, ?, ?, ?)",
                (orcid_id, publication_key, decision, _now()))

    def claim_decisions_for(self, orcid_id: str) -> set[str]:
        with self._connect() as con:
            rows = con.execute(
                "SELECT publication_key FROM claim_decisions"
                " WHERE orcid_id = ?", (orcid_id,)).fetchall()
        return {r["publication_key"] for r in rows}
```
If accounts.py would exceed ~350 lines, split the new methods into `app/repositories/engagement.py` as a mixin class `EngagementStoreMixin` that `AccountStore` inherits — schema stays in `_SCHEMA`; state in your report which shape you chose.

- [ ] **Step 4: Tests green + backend gauntlet**

Run: `.venv/Scripts/python -m pytest tests/test_engagement_store.py -v` → PASS.
Run: `.venv/Scripts/python -m scripts.gauntlet --backend-only` → all gates PASS.

- [ ] **Step 5: Commit**

```bash
git add ResearchSense/backend/app/repositories ResearchSense/backend/tests/test_engagement_store.py
git commit -m "feat: engagement store (follows, events, notifications, claim decisions)"
```

---

### Task 2: Fan-out + notification text (pure policy)

**Files:**
- Create: `ResearchSense/backend/app/services/engagement.py`
- Create: `ResearchSense/backend/tests/test_engagement_fanout.py`

**Interfaces:**
- Consumes: event dicts as returned by `events_since` ({id, kind, subject_id, payload, created_at}); follow dicts ({orcid_id, kind, target}); account dicts ({orcid_id, researcher_id}).
- Produces:
  - `fanout(events: list[dict], follows: list[dict], accounts: list[dict]) -> list[tuple[str, int]]` — (orcid_id, event_id) pairs, deduplicated.
  - `notification_text(event: dict) -> str` — human line per event kind (table-driven).

- [ ] **Step 1: Write the failing tests**

`tests/test_engagement_fanout.py`:
```python
from app.services.engagement import fanout, notification_text


def _ev(id, kind, subject_id=None, **payload):
    return {"id": id, "kind": kind, "subject_id": subject_id,
            "payload": payload, "created_at": "2026-07-31T00:00:00"}


ACCOUNTS = [{"orcid_id": "0000-1", "researcher_id": 7},
            {"orcid_id": "0000-2", "researcher_id": 9}]


def test_researcher_follower_gets_publication_added():
    events = [_ev(1, "publication_added", 7, title="T", topics=["AI"],
                  department="Psychology", author_ids=[7])]
    follows = [{"orcid_id": "0000-2", "kind": "researcher", "target": "7"}]
    assert fanout(events, follows, ACCOUNTS) == [("0000-2", 1)]


def test_topic_and_department_followers_match_payload():
    events = [_ev(2, "publication_added", 7, title="T", topics=["AI"],
                  department="Psychology", author_ids=[7])]
    follows = [{"orcid_id": "0000-2", "kind": "topic", "target": "AI"},
               {"orcid_id": "0000-2", "kind": "department", "target": "Law"}]
    assert fanout(events, follows, ACCOUNTS) == [("0000-2", 2)]


def test_subject_gets_own_lifecycle_events_without_follows():
    events = [_ev(3, "submission_approved", 7, title="T"),
              _ev(4, "claim_candidates", 9, candidates=[]),
              _ev(5, "recommendations_changed", 7, top=[9])]
    pairs = fanout(events, [], ACCOUNTS)
    assert ("0000-1", 3) in pairs and ("0000-2", 4) in pairs
    assert ("0000-1", 5) in pairs


def test_author_does_not_get_notified_of_own_paper_via_follow():
    events = [_ev(6, "publication_added", 7, title="T", topics=[],
                  department="", author_ids=[7])]
    follows = [{"orcid_id": "0000-1", "kind": "researcher", "target": "7"}]
    assert fanout(events, follows, ACCOUNTS) == []


def test_notification_text_per_kind():
    assert "approved" in notification_text(
        _ev(7, "submission_approved", 7, title="My Paper")).lower()
    assert "My Paper" in notification_text(
        _ev(8, "submission_approved", 7, title="My Paper"))
    line = notification_text(_ev(9, "claim_candidates", 9,
                                 candidates=[{"title": "A"}, {"title": "B"}]))
    assert "2" in line
```

- [ ] **Step 2: Run to verify failure** — module missing.

- [ ] **Step 3: Implement `app/services/engagement.py`**

```python
"""Engagement policy: who gets told about which event, and in what words.

Pure functions over immutable event/follow/account dicts. Mechanism
(SQLite writes, HTTP, email) lives elsewhere; this module decides.
"""
from __future__ import annotations

_SELF_KINDS = {"submission_approved", "submission_rejected",
               "claim_candidates", "recommendations_changed"}


def fanout(events: list[dict], follows: list[dict],
           accounts: list[dict]) -> list[tuple[str, int]]:
    orcid_of = {a["researcher_id"]: a["orcid_id"] for a in accounts}
    pairs: list[tuple[str, int]] = []
    seen: set[tuple[str, int]] = set()

    def add(orcid: str, event_id: int) -> None:
        if (orcid, event_id) not in seen:
            seen.add((orcid, event_id))
            pairs.append((orcid, event_id))

    for ev in events:
        if ev["kind"] in _SELF_KINDS:
            owner = orcid_of.get(ev["subject_id"])
            if owner:
                add(owner, ev["id"])
            continue
        if ev["kind"] != "publication_added":
            continue
        payload = ev["payload"]
        author_ids = set(payload.get("author_ids") or [])
        topics = set(payload.get("topics") or [])
        department = payload.get("department") or ""
        for f in follows:
            match = (
                (f["kind"] == "researcher" and f["target"].isdigit()
                 and int(f["target"]) in author_ids)
                or (f["kind"] == "topic" and f["target"] in topics)
                or (f["kind"] == "department" and f["target"] == department)
            )
            follower_rid = next(
                (a["researcher_id"] for a in accounts
                 if a["orcid_id"] == f["orcid_id"]), None)
            if match and follower_rid not in author_ids:
                add(f["orcid_id"], ev["id"])
    return pairs


_TEXTS = {
    "publication_added": lambda p: f'New publication: "{p.get("title", "")}"',
    "submission_approved": lambda p: (
        f'Your paper "{p.get("title", "")}" was approved and is now live'),
    "submission_rejected": lambda p: (
        f'Your paper "{p.get("title", "")}" was not approved'
        + (f' — {p["note"]}' if p.get("note") else "")),
    "claim_candidates": lambda p: (
        f'We found {len(p.get("candidates") or [])} paper(s) that might be'
        " yours — review them in your dashboard"),
    "recommendations_changed": lambda p: (
        "Your collaboration recommendations were refreshed"),
}


def notification_text(event: dict) -> str:
    render = _TEXTS.get(event["kind"])
    return render(event["payload"]) if render else event["kind"]
```

- [ ] **Step 4: Tests green + backend gauntlet** — `pytest tests/test_engagement_fanout.py -v` PASS; `python -m scripts.gauntlet --backend-only` PASS.

- [ ] **Step 5: Commit** — `git add app/services/engagement.py tests/test_engagement_fanout.py` (with backend prefix) → `git commit -m "feat: pure fan-out and notification text policy"`.

---

### Task 3: Follows + notifications API

**Files:**
- Create: `ResearchSense/backend/app/routers/engagement.py`
- Modify: `ResearchSense/backend/app/main.py` (include router — mirror how existing routers are included)
- Create: `ResearchSense/backend/tests/test_engagement_api.py`

**Interfaces:**
- Consumes: Task 1 store methods; `current_user` dependency + `_submitting_researcher`-style account resolution (read `app/routers/papers.py` and reuse its idiom).
- Produces (Task 9 frontend calls these):
  - `POST /api/engagement/follows` {kind, target} → {status:"following"}; `DELETE /api/engagement/follows` {kind, target} → {status:"unfollowed"}; `GET /api/engagement/follows` → list[{kind, target}]
  - `GET /api/engagement/notifications` → {unread: int, items: [{id, kind, text, read, created_at}]} (text via Task 2 `notification_text`)
  - `POST /api/engagement/notifications/read` {ids: [int]} → {status:"ok"}

- [ ] **Step 1: Write the failing tests**

`tests/test_engagement_api.py`:
```python
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
    app.dependency_overrides[security.current_user] = (
        lambda: {"role": "researcher", "sub": "0000-1"})
    AccountStore.instance().create_account("0000-1", 7, "x")
    yield TestClient(app)
    app.dependency_overrides.clear()
    AccountStore._instance = None


def test_follow_unfollow_roundtrip(client):
    assert client.post("/api/engagement/follows",
                       json={"kind": "topic", "target": "AI"}).status_code == 200
    assert client.get("/api/engagement/follows").json() == [
        {"kind": "topic", "target": "AI"}]
    client.request("DELETE", "/api/engagement/follows",
                   json={"kind": "topic", "target": "AI"})
    assert client.get("/api/engagement/follows").json() == []


def test_invalid_follow_kind_is_rejected(client):
    r = client.post("/api/engagement/follows",
                    json={"kind": "planet", "target": "Mars"})
    assert r.status_code == 422


def test_notifications_listing_and_read(client):
    store = AccountStore.instance()
    eid = store.append_event("submission_approved", 7, {"title": "T"})
    store.insert_notifications([("0000-1", eid)])
    data = client.get("/api/engagement/notifications").json()
    assert data["unread"] == 1 and "approved" in data["items"][0]["text"].lower()
    client.post("/api/engagement/notifications/read",
                json={"ids": [data["items"][0]["id"]]})
    assert client.get("/api/engagement/notifications").json()["unread"] == 0
```

- [ ] **Step 2: Run to verify failure** — 404s.

- [ ] **Step 3: Implement the router**

`app/routers/engagement.py` — thin, following papers.py's account-resolution idiom:
```python
"""Follow/subscribe + notification center endpoints (faculty auth)."""
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.core.security import current_user
from app.repositories.accounts import AccountStore
from app.services.engagement import notification_text

router = APIRouter(prefix="/api/engagement", tags=["engagement"])


class FollowBody(BaseModel):
    kind: Literal["researcher", "topic", "department"]
    target: str


class ReadBody(BaseModel):
    ids: list[int]


def _orcid(token_payload: dict = Depends(current_user)) -> str:
    if token_payload.get("role") != "researcher":
        raise HTTPException(status_code=403, detail="Faculty account required")
    account = AccountStore.instance().get_account(token_payload["sub"])
    if account is None or not account["active"]:
        raise HTTPException(status_code=401, detail="Account not found or disabled")
    return account["orcid_id"]


@router.post("/follows")
def follow(body: FollowBody, orcid: str = Depends(_orcid)):
    AccountStore.instance().add_follow(orcid, body.kind, body.target)
    return {"status": "following"}


@router.delete("/follows")
def unfollow(body: FollowBody, orcid: str = Depends(_orcid)):
    AccountStore.instance().remove_follow(orcid, body.kind, body.target)
    return {"status": "unfollowed"}


@router.get("/follows")
def my_follows(orcid: str = Depends(_orcid)):
    return [{"kind": f["kind"], "target": f["target"]}
            for f in AccountStore.instance().follows_for(orcid)]


@router.get("/notifications")
def notifications(orcid: str = Depends(_orcid)):
    store = AccountStore.instance()
    items = [{"id": n["id"], "kind": n["kind"],
              "text": notification_text(n), "read": bool(n["read"]),
              "created_at": n["created_at"]}
             for n in store.notifications_for(orcid)]
    return {"unread": store.unread_count(orcid), "items": items}


@router.post("/notifications/read")
def read(body: ReadBody, orcid: str = Depends(_orcid)):
    AccountStore.instance().mark_read(orcid, body.ids)
    return {"status": "ok"}
```
Include in `app/main.py` exactly as the other routers are included (read the file; typically `app.include_router(engagement.router)` with the matching import).
Note: `notification_text` receives the joined row from `notifications_for` — it has `kind` and `payload` keys, satisfying the event-dict contract.

- [ ] **Step 4: Tests green + backend gauntlet.**

- [ ] **Step 5: Commit** — `git commit -m "feat: follows and notification center API"` (router, main.py, test file only).

---

### Task 4: Bibliometrics (pure + pipeline + schema)

**Files:**
- Create: `ResearchSense/backend/scripts/bibliometrics.py`
- Modify: `ResearchSense/backend/scripts/fetch_publications.py` (call at the researcher-enrichment stage, after `pubs_of` is built)
- Modify: `ResearchSense/backend/app/schemas/researcher.py` (`ResearcherDetail.bibliometrics: dict = {}` and `Researcher.bibliometrics: dict = {}`)
- Create: `ResearchSense/backend/tests/test_bibliometrics.py`

**Interfaces:**
- Produces: `compute_bibliometrics(pubs: list[dict], now_year: int) -> dict` returning exactly `{"h_index": int, "i10": int, "citations_total": int, "citation_velocity": int, "citations_by_year": [{"year": int, "citations": int}]}` — stored on each researcher record as `bibliometrics`; consumed by Task 7 (digest) and Task 10 (frontend).

- [ ] **Step 1: Write the failing tests**

`tests/test_bibliometrics.py`:
```python
from scripts.bibliometrics import compute_bibliometrics


def _p(year, cites):
    return {"publication_year": year, "citation_count": cites}


def test_h_index_classic_cases():
    pubs = [_p(2020, c) for c in [10, 8, 5, 4, 3]]
    assert compute_bibliometrics(pubs, 2026)["h_index"] == 4
    assert compute_bibliometrics([], 2026)["h_index"] == 0
    assert compute_bibliometrics([_p(2020, 0)], 2026)["h_index"] == 0


def test_i10_counts_papers_with_ten_plus():
    pubs = [_p(2020, 10), _p(2021, 9), _p(2022, 25)]
    assert compute_bibliometrics(pubs, 2026)["i10"] == 2


def test_velocity_is_recent_two_years_only():
    pubs = [_p(2025, 7), _p(2026, 3), _p(2020, 100)]
    assert compute_bibliometrics(pubs, 2026)["citation_velocity"] == 10


def test_citations_by_year_last_five_years_sorted():
    pubs = [_p(2022, 5), _p(2024, 2), _p(2019, 9)]
    series = compute_bibliometrics(pubs, 2026)["citations_by_year"]
    assert series == [{"year": 2022, "citations": 5},
                      {"year": 2024, "citations": 2}]
```

- [ ] **Step 2: Run to verify failure.**

- [ ] **Step 3: Implement `scripts/bibliometrics.py`**

```python
"""Per-researcher bibliometrics, computed at pipeline time (pure)."""
from __future__ import annotations


def compute_bibliometrics(pubs: list[dict], now_year: int) -> dict:
    citations = sorted((p.get("citation_count", 0) for p in pubs), reverse=True)
    h = 0
    for i, c in enumerate(citations, start=1):
        if c >= i:
            h = i
        else:
            break
    by_year: dict[int, int] = {}
    for p in pubs:
        year = p.get("publication_year") or 0
        if year > now_year - 5 and year <= now_year:
            by_year[year] = by_year.get(year, 0) + p.get("citation_count", 0)
    return {
        "h_index": h,
        "i10": sum(1 for c in citations if c >= 10),
        "citations_total": sum(citations),
        "citation_velocity": sum(
            p.get("citation_count", 0) for p in pubs
            if (p.get("publication_year") or 0) >= now_year - 1),
        "citations_by_year": [
            {"year": y, "citations": by_year[y]} for y in sorted(by_year)],
    }
```
Wire into `fetch_publications.py` in the researcher-enrichment loop (where `research_areas` is set — `mine` is that researcher's publications):
```python
        from datetime import date
        r["bibliometrics"] = compute_bibliometrics(mine, date.today().year)
```
(Import `compute_bibliometrics` at the top with the other script imports; hoist the `date` import to module level.) Add the schema fields with `= {}` defaults (old data stays loadable).

- [ ] **Step 4: Tests green (`pytest tests/test_bibliometrics.py -v`), import smoke (`python -c "import scripts.fetch_publications"`), backend gauntlet.**

- [ ] **Step 5: Commit** — `git commit -m "feat: per-researcher bibliometrics at pipeline time"`.

---

### Task 5: Proactive recommender (pure + pipeline + event)

**Files:**
- Create: `ResearchSense/backend/scripts/recommender.py`
- Modify: `ResearchSense/backend/scripts/fetch_publications.py` (compute + store after bibliometrics)
- Modify: `ResearchSense/backend/app/services/refresh_service.py` (emit `recommendations_changed` events after refresh — see Step 5)
- Modify: `ResearchSense/backend/app/schemas/researcher.py` (`recommended_collaborators: list[dict] = []` on `ResearcherDetail`)
- Create: `ResearchSense/backend/tests/test_recommender.py`

**Interfaces:**
- Produces: `recommend(researchers: list[dict], publications: list[dict], top_n: int = 5) -> dict[int, list[dict]]` — per researcher_id, list of `{"researcher_id", "full_name", "score", "reasons": [str]}`; stored on researcher records as `recommended_collaborators`. Weights table `WEIGHTS = {"adamic_adar": 1.0, "topic_overlap": 1.0, "same_campus": 0.25, "cross_dept_shared_topic": 0.25}`.

- [ ] **Step 1: Write the failing tests**

`tests/test_recommender.py`:
```python
from scripts.recommender import recommend


def _r(rid, name, topics, campus="K", dept="CS"):
    return {"researcher_id": rid, "full_name": name, "campus": campus,
            "department": dept,
            "topics": [{"topic_id": hash(t) % 1000, "topic_name": t}
                       for t in topics]}


def _pub(*rids):
    return {"authors": [{"researcher_id": r} for r in rids]}


def test_existing_coauthors_are_never_recommended():
    rs = [_r(1, "A", ["AI"]), _r(2, "B", ["AI"])]
    recs = recommend(rs, [_pub(1, 2)])
    assert all(c["researcher_id"] != 2 for c in recs.get(1, []))


def test_mutual_coauthor_link_prediction_ranks_first():
    # 1-3 and 2-3 published; 1-2 never did -> 3 is their mutual neighbor.
    rs = [_r(1, "A", []), _r(2, "B", []), _r(3, "C", []), _r(4, "D", [])]
    recs = recommend(rs, [_pub(1, 3), _pub(2, 3)])
    assert recs[1][0]["researcher_id"] == 2
    assert any("mutual co-author" in reason
               for reason in recs[1][0]["reasons"])


def test_shared_topic_recommendation_carries_reason():
    rs = [_r(1, "A", ["Deep Learning"]), _r(2, "B", ["Deep Learning"],
                                            dept="EE")]
    recs = recommend(rs, [])
    assert recs[1][0]["researcher_id"] == 2
    assert any("Deep Learning" in reason for reason in recs[1][0]["reasons"])


def test_no_signal_no_recommendation():
    rs = [_r(1, "A", ["AI"]), _r(2, "B", ["Law"], campus="L", dept="Law")]
    assert recs_empty(recommend(rs, []))


def recs_empty(recs):
    return all(not v for v in recs.values())


def test_top_n_cap():
    rs = [_r(i, f"R{i}", ["AI"]) for i in range(1, 10)]
    recs = recommend(rs, [], top_n=5)
    assert len(recs[1]) == 5
```

- [ ] **Step 2: Run to verify failure.**

- [ ] **Step 3: Implement `scripts/recommender.py`**

```python
"""Proactive collaboration recommender (pipeline-time, pure, explainable).

Link prediction over the co-authorship graph (Adamic-Adar) blended with
topic overlap and small locality bonuses. Every scoring component yields a
human-readable reason, so recommendations are explainable by construction.
"""
from __future__ import annotations

import math
from collections import defaultdict

WEIGHTS = {"adamic_adar": 1.0, "topic_overlap": 1.0,
           "same_campus": 0.25, "cross_dept_shared_topic": 0.25}


def _graph(publications: list[dict]) -> dict[int, dict[int, int]]:
    edges: dict[int, dict[int, int]] = defaultdict(lambda: defaultdict(int))
    for p in publications:
        ids = [a["researcher_id"] for a in p.get("authors", [])
               if a.get("researcher_id") is not None]
        for i in ids:
            for j in ids:
                if i != j:
                    edges[i][j] += 1
    return edges


def recommend(researchers: list[dict], publications: list[dict],
              top_n: int = 5) -> dict[int, list[dict]]:
    edges = _graph(publications)
    topics_of = {r["researcher_id"]:
                 {t["topic_name"] for t in r.get("topics", [])}
                 for r in researchers}
    by_id = {r["researcher_id"]: r for r in researchers}
    out: dict[int, list[dict]] = {}

    for r in researchers:
        rid = r["researcher_id"]
        my_topics = topics_of[rid]
        my_neighbors = set(edges.get(rid, {}))
        scored: list[dict] = []
        for other in researchers:
            oid = other["researcher_id"]
            if oid == rid or oid in my_neighbors:
                continue
            mutual = my_neighbors & set(edges.get(oid, {}))
            aa = sum(1.0 / math.log(max(len(edges[m]), 2)) for m in mutual)
            shared = my_topics & topics_of[oid]
            union = my_topics | topics_of[oid]
            overlap = len(shared) / len(union) if union else 0.0
            score = (WEIGHTS["adamic_adar"] * aa
                     + WEIGHTS["topic_overlap"] * overlap)
            reasons: list[str] = []
            if mutual:
                reasons.append(f"{len(mutual)} mutual co-author"
                               + ("s" if len(mutual) > 1 else ""))
            if shared:
                reasons.append("both publish in "
                               + ", ".join(sorted(shared)[:2]))
            if score > 0 and r.get("campus") == other.get("campus"):
                score += WEIGHTS["same_campus"]
                reasons.append("same campus")
            if shared and r.get("department") != other.get("department"):
                score += WEIGHTS["cross_dept_shared_topic"]
                reasons.append("cross-department match")
            if score > 0 and reasons:
                scored.append({"researcher_id": oid,
                               "full_name": other["full_name"],
                               "score": round(score, 3),
                               "reasons": reasons})
        scored.sort(key=lambda c: -c["score"])
        out[rid] = scored[:top_n]
    return out
```
Wire into `fetch_publications.py` after the bibliometrics loop:
```python
    recs = recommend(researchers, publications)
    for r in researchers:
        r["recommended_collaborators"] = recs.get(r["researcher_id"], [])
```
(import `recommend` at top). Add the schema field.

- [ ] **Step 4: Emit `recommendations_changed` on refresh**

In `refresh_service.run_refresh`, BEFORE `fetch_publications.main()`, snapshot current recommendations:
```python
        import json as _json
        from pathlib import Path
        data_dir = Path(__file__).resolve().parents[1] / "data"
        def _rec_map():
            rs = _json.loads((data_dir / "researchers.json").read_text("utf-8"))
            return {r["researcher_id"]:
                    [c["researcher_id"]
                     for c in r.get("recommended_collaborators", [])]
                    for r in rs}
        before = _rec_map()
```
AFTER the index rebuild + cache clears:
```python
        after = _rec_map()
        for rid, top in after.items():
            if top and top != before.get(rid):
                store.append_event("recommendations_changed", rid,
                                   {"top": top})
```
(`store` is the `AccountStore` already in scope there.)

- [ ] **Step 5: Tests green, import smoke on fetch_publications + refresh_service, backend gauntlet.**

- [ ] **Step 6: Commit** — `git commit -m "feat: explainable proactive collaboration recommender"`.

---

### Task 6: Claim candidates (pipeline capture + API)

**Files:**
- Modify: `ResearchSense/backend/scripts/fetch_publications.py` (collect near-miss matches → `app/data/claim_candidates.json`)
- Create: `ResearchSense/backend/app/services/claims_service.py`
- Create: `ResearchSense/backend/app/routers/claims.py` (+ include in main.py)
- Modify: `ResearchSense/backend/app/services/refresh_service.py` (emit `claim_candidates` events after refresh)
- Create: `ResearchSense/backend/tests/test_claims.py`

**Interfaces:**
- Pipeline artifact `app/data/claim_candidates.json`: `[{researcher_id, publication_key, title, journal_name, publication_year, doi}]` — a near-miss = fuzzy name match (`_fuzzy_name_match`) that was NOT auto-linked (field guard failed and unanchored, or >1 roster candidate). `publication_key` = `dedupe_key(doi, title, year)` from `scripts.fetch_sources`.
- `claims_service.pending_for(researcher_id: int, orcid_id: str) -> list[dict]` (candidates minus decided keys)
- `claims_service.accept(orcid_id: str, researcher_id: int, publication_key: str) -> dict` — links the author row in publications.json (sets researcher_id on the fuzzy-matched author entry), bumps counts, appends fact-card chunk via `submission_service._index_chunk`-style embed (reuse `staging`-free direct append: call `app.services.rag.indexer.append_chunks` with one fact-card), records decision. Idempotent: already-decided or already-linked → no-op result `{"status": "already-done"}`.
- `claims_service.decline(orcid_id, publication_key) -> dict` — records decision only.
- API (faculty auth, same `_orcid`-style resolution as Task 3 but ALSO resolving researcher_id): `GET /api/claims/mine`, `POST /api/claims/accept` {publication_key}, `POST /api/claims/decline` {publication_key}.

- [ ] **Step 1: Write the failing tests**

`tests/test_claims.py`:
```python
import json

import pytest

import app.repositories.accounts as accounts_mod
import app.services.claims_service as svc
from app.repositories.accounts import AccountStore


@pytest.fixture()
def store(tmp_path, monkeypatch):
    monkeypatch.setattr(accounts_mod, "DB_PATH", tmp_path / "t.db")
    AccountStore._instance = None
    yield AccountStore.instance()
    AccountStore._instance = None


CANDS = [{"researcher_id": 7, "publication_key": "doi:10.1/a", "title": "A",
          "journal_name": "J", "publication_year": 2024, "doi": "10.1/a"},
         {"researcher_id": 7, "publication_key": "ty:b:2023", "title": "B",
          "journal_name": "J", "publication_year": 2023, "doi": None}]


def test_pending_excludes_decided(store, monkeypatch):
    monkeypatch.setattr(svc, "_candidates", lambda: CANDS)
    store.record_claim_decision("0000-1", "doi:10.1/a", "declined")
    pending = svc.pending_for(7, "0000-1")
    assert [c["publication_key"] for c in pending] == ["ty:b:2023"]


def test_decline_records_decision(store, monkeypatch):
    monkeypatch.setattr(svc, "_candidates", lambda: CANDS)
    svc.decline("0000-1", "doi:10.1/a")
    assert "doi:10.1/a" in store.claim_decisions_for("0000-1")


def test_accept_links_author_and_is_idempotent(store, monkeypatch, tmp_path):
    monkeypatch.setattr(svc, "_candidates", lambda: CANDS)
    pubs = [{"publication_id": 1, "title": "A", "doi": "10.1/a",
             "publication_year": 2024, "journal_name": "J",
             "publication_type": "journal", "citation_count": 3, "campus": "K",
             "authors": [{"researcher_id": None, "full_name": "S Khan",
                          "order": 1}], "topics": []}]
    pubs_path = tmp_path / "publications.json"
    pubs_path.write_text(json.dumps(pubs), "utf-8")
    rs_path = tmp_path / "researchers.json"
    rs_path.write_text(json.dumps([
        {"researcher_id": 7, "full_name": "Sana Khan",
         "publication_count": 0, "citation_count": 0}]), "utf-8")
    monkeypatch.setattr(svc, "PUBS_PATH", pubs_path)
    monkeypatch.setattr(svc, "RESEARCHERS_PATH", rs_path)
    monkeypatch.setattr(svc, "_append_fact_card", lambda record: None)
    monkeypatch.setattr(svc, "_clear_caches", lambda: None)

    out = svc.accept("0000-1", 7, "doi:10.1/a")
    assert out["status"] == "accepted"
    linked = json.loads(pubs_path.read_text("utf-8"))
    assert linked[0]["authors"][0]["researcher_id"] == 7
    rs = json.loads(rs_path.read_text("utf-8"))
    assert rs[0]["publication_count"] == 1 and rs[0]["citation_count"] == 3

    assert svc.accept("0000-1", 7, "doi:10.1/a")["status"] == "already-done"
```

- [ ] **Step 2: Run to verify failure.**

- [ ] **Step 3: Implement `app/services/claims_service.py`**

```python
"""Per-faculty claim loop: near-miss publication matches become questions.

Candidates are produced by the pipeline (claim_candidates.json); decisions
live in SQLite (never re-ask); accepting links authorship, updates counts,
and adds the paper's fact-card to the live index.
"""
from __future__ import annotations

import json
from pathlib import Path

from app.repositories import loader
from app.repositories.accounts import AccountStore

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
CANDIDATES_PATH = DATA_DIR / "claim_candidates.json"
PUBS_PATH = DATA_DIR / "publications.json"
RESEARCHERS_PATH = DATA_DIR / "researchers.json"


class ClaimError(Exception):
    """User-facing claim failure."""


def _candidates() -> list[dict]:
    if CANDIDATES_PATH.exists():
        return json.loads(CANDIDATES_PATH.read_text("utf-8"))
    return []


def pending_for(researcher_id: int, orcid_id: str) -> list[dict]:
    decided = AccountStore.instance().claim_decisions_for(orcid_id)
    return [c for c in _candidates()
            if c["researcher_id"] == researcher_id
            and c["publication_key"] not in decided]


def decline(orcid_id: str, publication_key: str) -> dict:
    AccountStore.instance().record_claim_decision(
        orcid_id, publication_key, "declined")
    return {"status": "declined"}


def _append_fact_card(record: dict) -> None:
    from app.services.rag import indexer
    authors = ", ".join(a["full_name"] for a in record["authors"][:8])
    text = (f'Publication: "{record["title"]}" ({record["publication_year"]}),'
            f' {record["publication_type"]} in {record["journal_name"]}.'
            f" Authors: {authors}. Citations: {record['citation_count']}."
            f" Campus: {record['campus']}.")
    indexer.append_chunks([{
        "text": text, "kind": "publication", "ref_id": None,
        "label": f"{record['title'][:70]} ({record['publication_year']})"}])


def _clear_caches() -> None:
    loader.clear_cache()


def accept(orcid_id: str, researcher_id: int, publication_key: str) -> dict:
    store = AccountStore.instance()
    if publication_key in store.claim_decisions_for(orcid_id):
        return {"status": "already-done"}
    pubs = json.loads(PUBS_PATH.read_text("utf-8"))
    from scripts.fetch_sources import dedupe_key
    target = next(
        (p for p in pubs
         if dedupe_key(p.get("doi"), p.get("title", ""),
                       p.get("publication_year", 0)) == publication_key), None)
    if target is None:
        store.record_claim_decision(orcid_id, publication_key, "accepted")
        raise ClaimError("This paper is no longer in the database.")
    if any(a.get("researcher_id") == researcher_id
           for a in target.get("authors", [])):
        store.record_claim_decision(orcid_id, publication_key, "accepted")
        return {"status": "already-done"}

    from scripts.fetch_publications import _fuzzy_name_match
    researchers = json.loads(RESEARCHERS_PATH.read_text("utf-8"))
    me = next(r for r in researchers if r["researcher_id"] == researcher_id)
    slot = next((a for a in target["authors"]
                 if a.get("researcher_id") is None
                 and _fuzzy_name_match(me["full_name"], a["full_name"])),
                None)
    if slot is None:
        slot = {"researcher_id": None, "full_name": me["full_name"],
                "order": len(target["authors"]) + 1}
        target["authors"].append(slot)
    slot["researcher_id"] = researcher_id
    me["publication_count"] = me.get("publication_count", 0) + 1
    me["citation_count"] = (me.get("citation_count", 0)
                            + target.get("citation_count", 0))
    PUBS_PATH.write_text(json.dumps(pubs, indent=2, ensure_ascii=False),
                         "utf-8")
    RESEARCHERS_PATH.write_text(
        json.dumps(researchers, indent=2, ensure_ascii=False), "utf-8")
    store.record_claim_decision(orcid_id, publication_key, "accepted")
    _clear_caches()
    try:
        _append_fact_card(target)
    except Exception:  # noqa: BLE001 - linked; index rebuild covers it
        pass
    return {"status": "accepted", "title": target["title"]}
```

- [ ] **Step 4: Pipeline capture in fetch_publications.py**

In the fuzzy second pass, matches currently skipped by `len(cands) != 1` or the guard now also append to a module-level collection. Concretely: initialize `claim_candidates: list[dict] = []` in `main()` before the per-work loop; in the fuzzy pass replace
```python
            if len(cands) != 1:
                continue
```
with
```python
            if len(cands) != 1:
                for cand in cands:
                    claim_candidates.append((cand["researcher_id"], w))
                continue
```
and where the guard rejects (`if not anchored and not expertise_field_guard(...)`): `claim_candidates.append((rid, w))` before `continue`.
After the loop (near where publications.json is written), dedupe + write:
```python
    seen_keys: set[tuple[int, str]] = set()
    cand_rows: list[dict] = []
    for rid, w in claim_candidates:
        key = dedupe_key((w.get("doi") or "").replace("https://doi.org/", "")
                         or None,
                         clean_title(w.get("title") or ""),
                         w.get("publication_year") or 0)
        if (rid, key) in seen_keys:
            continue
        seen_keys.add((rid, key))
        venue, wtype = venue_of(w)
        cand_rows.append({
            "researcher_id": rid, "publication_key": key,
            "title": clean_title(w.get("title") or ""),
            "journal_name": venue,
            "publication_year": w.get("publication_year") or 0,
            "doi": (w.get("doi") or "").replace("https://doi.org/", "") or None,
        })
    (DATA_DIR / "claim_candidates.json").write_text(
        json.dumps(cand_rows, indent=2, ensure_ascii=False), "utf-8")
    print(f"  {len(cand_rows)} claim candidate(s) for faculty review")
```

- [ ] **Step 5: API router `app/routers/claims.py`**

```python
"""Per-faculty publication claim endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.core.security import current_user
from app.repositories.accounts import AccountStore
from app.services import claims_service
from app.services.claims_service import ClaimError

router = APIRouter(prefix="/api/claims", tags=["claims"])


class ClaimBody(BaseModel):
    publication_key: str


def _account(token_payload: dict = Depends(current_user)) -> dict:
    if token_payload.get("role") != "researcher":
        raise HTTPException(status_code=403, detail="Faculty account required")
    account = AccountStore.instance().get_account(token_payload["sub"])
    if account is None or not account["active"]:
        raise HTTPException(status_code=401, detail="Account not found or disabled")
    return account


@router.get("/mine")
def mine(account: dict = Depends(_account)):
    return claims_service.pending_for(account["researcher_id"],
                                      account["orcid_id"])


@router.post("/accept")
def accept(body: ClaimBody, account: dict = Depends(_account)):
    try:
        return claims_service.accept(account["orcid_id"],
                                     account["researcher_id"],
                                     body.publication_key)
    except ClaimError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.post("/decline")
def decline(body: ClaimBody, account: dict = Depends(_account)):
    return claims_service.decline(account["orcid_id"], body.publication_key)
```
Include in main.py. In `refresh_service.run_refresh`, after the refresh completes, group the fresh `claim_candidates.json` by researcher and `store.append_event("claim_candidates", rid, {"candidates": [{"title": c["title"], "publication_key": c["publication_key"]} for c in group]})` for each researcher with a non-empty group, then run fan-out (Task 7 wires the shared fan-out call; here just append the events — if Task 7 landed first, its post-refresh hook picks them up automatically).

- [ ] **Step 6: Tests green + backend gauntlet.**

- [ ] **Step 7: Commit** — `git commit -m "feat: per-faculty new-paper claim loop"`.

---

### Task 7: Digest + fan-out wiring + optional SMTP

**Files:**
- Create: `ResearchSense/backend/app/services/digest_service.py`
- Modify: `ResearchSense/backend/app/services/refresh_service.py` (post-refresh: fan-out + digest email)
- Modify: `ResearchSense/backend/app/routers/engagement.py` (add `GET /api/engagement/digest`)
- Modify: `ResearchSense/backend/app/services/submission_service.py` + `app/routers/admin.py` (append `submission_approved` / `submission_rejected` events at approve/reject; `publication_added` for approved papers)
- Create: `ResearchSense/backend/tests/test_digest.py`

**Interfaces:**
- Consumes: Tasks 1-2 store + fanout; Task 4 `bibliometrics` on researcher records.
- Produces:
  - `build_digest(events: list[dict], follows: list[dict], researcher: dict, window_days: int = 7) -> dict` — `{"new_papers": [...], "my_updates": [...], "pending_claims": int, "top_recommendation": dict | None, "metrics": dict}`
  - `smtp_config() -> dict | None` — None when no SMTP env vars set; raises `ValueError` on partial config; keys host/port/user/password/sender.
  - `send_digest_email(cfg: dict, to_addr: str, digest: dict) -> None` (smtplib, 10 s timeout, plain text).
  - `run_engagement_post_refresh() -> None` — appends `publication_added` events for publications new since the last refresh (diff by `dedupe_key` snapshot), runs `fanout` over new events, inserts notifications, then digest emails when configured. Called at the end of `refresh_service.run_refresh`.
  - `GET /api/engagement/digest` → the current user's digest (window 7 days).

- [ ] **Step 1: Write the failing tests**

`tests/test_digest.py`:
```python
import pytest

from app.services.digest_service import build_digest, smtp_config


def _ev(id, kind, subject_id=None, **payload):
    return {"id": id, "kind": kind, "subject_id": subject_id,
            "payload": payload, "created_at": "2026-07-30T00:00:00"}


ME = {"researcher_id": 7, "full_name": "Sana Khan",
      "bibliometrics": {"h_index": 4, "citations_total": 120},
      "recommended_collaborators": [
          {"researcher_id": 9, "full_name": "B", "score": 1.2,
           "reasons": ["both publish in AI"]}]}


def test_digest_sections():
    events = [
        _ev(1, "publication_added", 8, title="P1", topics=["AI"],
            department="CS", author_ids=[8]),
        _ev(2, "submission_approved", 7, title="Mine"),
        _ev(3, "claim_candidates", 7, candidates=[{"title": "C1"}]),
    ]
    follows = [{"orcid_id": "0000-1", "kind": "topic", "target": "AI"}]
    d = build_digest(events, follows, ME)
    assert [p["title"] for p in d["new_papers"]] == ["P1"]
    assert "Mine" in d["my_updates"][0]
    assert d["pending_claims"] == 1
    assert d["top_recommendation"]["full_name"] == "B"
    assert d["metrics"]["h_index"] == 4


def test_smtp_config_absent_is_none(monkeypatch):
    for var in ("SMTP_HOST", "SMTP_PORT", "SMTP_USER", "SMTP_PASS",
                "SMTP_FROM"):
        monkeypatch.delenv(var, raising=False)
    assert smtp_config() is None


def test_smtp_partial_config_fails_fast(monkeypatch):
    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
    for var in ("SMTP_PORT", "SMTP_USER", "SMTP_PASS", "SMTP_FROM"):
        monkeypatch.delenv(var, raising=False)
    with pytest.raises(ValueError):
        smtp_config()


def test_smtp_full_config_parsed(monkeypatch):
    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("SMTP_PORT", "587")
    monkeypatch.setenv("SMTP_USER", "u")
    monkeypatch.setenv("SMTP_PASS", "p")
    monkeypatch.setenv("SMTP_FROM", "noreply@example.com")
    cfg = smtp_config()
    assert cfg["port"] == 587 and cfg["sender"] == "noreply@example.com"
```

- [ ] **Step 2: Run to verify failure.**

- [ ] **Step 3: Implement `app/services/digest_service.py`**

```python
"""Weekly digest: pure builder + delivery edges (page always, email opt-in).

SMTP activates only when ALL of SMTP_HOST/PORT/USER/PASS/FROM are set;
partial config fails fast; none is a logged no-op.
"""
from __future__ import annotations

import logging
import os
import smtplib
from email.message import EmailMessage

from app.services.engagement import fanout, notification_text

log = logging.getLogger("researchsense.digest")

_SMTP_VARS = ("SMTP_HOST", "SMTP_PORT", "SMTP_USER", "SMTP_PASS", "SMTP_FROM")


def build_digest(events: list[dict], follows: list[dict], researcher: dict,
                 window_days: int = 7) -> dict:
    rid = researcher["researcher_id"]
    mine = [e for e in events if e["subject_id"] == rid]
    followed_pairs = {eid for _, eid in fanout(
        events, follows, [{"orcid_id": "me", "researcher_id": rid}])}
    new_papers = [
        {"title": e["payload"].get("title", ""),
         "topics": e["payload"].get("topics", [])}
        for e in events
        if e["kind"] == "publication_added" and e["id"] in followed_pairs]
    my_updates = [notification_text(e) for e in mine
                  if e["kind"] in ("submission_approved",
                                   "submission_rejected")]
    pending_claims = sum(
        len(e["payload"].get("candidates") or []) for e in mine
        if e["kind"] == "claim_candidates")
    recs = researcher.get("recommended_collaborators") or []
    return {
        "new_papers": new_papers,
        "my_updates": my_updates,
        "pending_claims": pending_claims,
        "top_recommendation": recs[0] if recs else None,
        "metrics": researcher.get("bibliometrics") or {},
    }


def smtp_config() -> dict | None:
    values = {v: os.environ.get(v) for v in _SMTP_VARS}
    present = [v for v, val in values.items() if val]
    if not present:
        return None
    missing = [v for v, val in values.items() if not val]
    if missing:
        raise ValueError(f"Partial SMTP config: missing {missing}")
    return {"host": values["SMTP_HOST"], "port": int(values["SMTP_PORT"]),
            "user": values["SMTP_USER"], "password": values["SMTP_PASS"],
            "sender": values["SMTP_FROM"]}


def render_text(digest: dict) -> str:
    lines = ["Your ResearchSense weekly digest", ""]
    if digest["new_papers"]:
        lines.append("New papers in your areas:")
        lines += [f"  - {p['title']}" for p in digest["new_papers"][:10]]
    if digest["my_updates"]:
        lines.append("Your submissions:")
        lines += [f"  - {u}" for u in digest["my_updates"]]
    if digest["pending_claims"]:
        lines.append(f"You have {digest['pending_claims']} paper(s) to "
                     "confirm in your dashboard.")
    if digest["top_recommendation"]:
        rec = digest["top_recommendation"]
        lines.append(f"Suggested collaborator: {rec['full_name']} "
                     f"({'; '.join(rec['reasons'])})")
    return "\n".join(lines)


def send_digest_email(cfg: dict, to_addr: str, digest: dict) -> None:
    msg = EmailMessage()
    msg["Subject"] = "Your ResearchSense weekly digest"
    msg["From"] = cfg["sender"]
    msg["To"] = to_addr
    msg.set_content(render_text(digest))
    with smtplib.SMTP(cfg["host"], cfg["port"], timeout=10) as smtp:
        smtp.starttls()
        smtp.login(cfg["user"], cfg["password"])
        smtp.send_message(msg)
```
Then `run_engagement_post_refresh()` in the same module: reads a snapshot file `app/data/.last_refresh_keys.json` (set of publication dedupe keys from the previous run; missing file = first run, snapshot only, no events), diffs current publications.json to find new keys, appends one `publication_added` event per new publication (payload: title, topics (topic_names), department of first linked author, author_ids), rewrites the snapshot, then: `events = store.events_since(<refresh start time>)`, `pairs = fanout(events, store.all_follows(), store.list_accounts_with_researcher_ids())` — add a tiny store helper or reuse `list_accounts()` rows (they carry orcid_id + researcher_id), `store.insert_notifications(pairs)`; finally `cfg = smtp_config()` inside try/except ValueError (log the error, skip email), and when cfg: for each active account with an email on their researcher record, `send_digest_email` in try/except per user (log + continue). Call `run_engagement_post_refresh()` at the end of `refresh_service.run_refresh` inside the existing try block, wrapped so failure logs but does not mark the refresh failed.

- [ ] **Step 4: Approval/rejection events**

In `app/routers/admin.py` `approve_paper`: after `set_submission_status`, append events —
```python
    record = json.loads(sub["record_json"])
    store.append_event("submission_approved", sub["researcher_id"],
                       {"title": sub["title"]})
    if sub["kind"] == "publication":
        store.append_event("publication_added", sub["researcher_id"], {
            "title": record.get("title", ""),
            "topics": [t.get("topic_name") for t in record.get("topics", [])],
            "department": "",
            "author_ids": [a.get("researcher_id")
                           for a in record.get("authors", [])
                           if a.get("researcher_id") is not None]})
    pairs = fanout(store.events_since(_now_minus_minutes(1)),
                   store.all_follows(), store.list_accounts())
    store.insert_notifications(pairs)
```
Simplify: add module helper `_now_minus_minutes` or just fan out the two fresh events directly by constructing the event dicts from the append_event return ids. Implementer choice; the contract is: approving creates the two events AND their notifications immediately. `reject_paper` appends `submission_rejected` with the note and fans out likewise. Add `GET /api/engagement/digest` to the engagement router: resolve account → researcher record (via loader) → `build_digest(store.events_since(<7 days ago>), store.follows_for(orcid), researcher_record)`.

- [ ] **Step 5: Tests green + backend gauntlet; extend test_admin_approval.py with one test: approving appends `submission_approved` + `publication_added` events and a notification for the submitter (query the store after approve).**

- [ ] **Step 6: Commit** — `git commit -m "feat: weekly digest, refresh fan-out, approval events, optional SMTP"`.

---

### Task 8: SSE streaming chat (backend)

**Files:**
- Modify: `ResearchSense/backend/app/services/chat_service.py` (add `stream_answer`)
- Modify: `ResearchSense/backend/app/routers/chat.py` (add `POST /stream`)
- Read first: `app/services/rag/agentic.py` (the 3-pass pipeline + Groq client usage)
- Create: `ResearchSense/backend/tests/test_chat_stream.py`

**Interfaces:**
- Produces: `ChatService.stream_answer(message: str, history) -> Iterator[dict]` yielding, in order: one `{"type": "sources", "sources": [...]}` (same source payload as the non-streaming path), then ≥1 `{"type": "token", "text": str}`, then `{"type": "done", "used_llm": bool}`; on exception `{"type": "error", "message": str}` then stop. Router wraps each dict as an SSE `data: <json>\n\n` line via `StreamingResponse(..., media_type="text/event-stream")`.
- Streaming rule: read `agentic.py`; if the final synthesis call can pass `stream=True` to the Groq SDK, add a streaming variant of ONLY that pass (intent/evidence passes unchanged) exposed as `agentic.run_agentic_pipeline_streaming(...) -> Iterator[str]`. If the SDK call shape makes that unreasonable, fall back to: run the existing non-streaming pipeline, then yield the final answer in ~60-character chunks (progressive UX preserved; state which route you took in the report).

- [ ] **Step 1: Write the failing test**

`tests/test_chat_stream.py`:
```python
import json

from fastapi.testclient import TestClient


def test_stream_endpoint_emits_sources_tokens_done(monkeypatch):
    from app import main as main_mod
    from app.services import chat_service as cs

    def fake_stream(self, message, history=None):
        yield {"type": "sources", "sources": []}
        yield {"type": "token", "text": "Hello "}
        yield {"type": "token", "text": "world"}
        yield {"type": "done", "used_llm": False}

    monkeypatch.setattr(cs.ChatService, "stream_answer", fake_stream)
    client = TestClient(main_mod.app)
    with client.stream("POST", "/api/chat/stream",
                       json={"message": "hi", "history": []}) as resp:
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/event-stream")
        events = []
        for line in resp.iter_lines():
            if line.startswith("data: "):
                events.append(json.loads(line[6:]))
    types = [e["type"] for e in events]
    assert types == ["sources", "token", "token", "done"]
    assert "".join(e.get("text", "") for e in events) == "Hello world"


def test_stream_error_event_on_failure(monkeypatch):
    from app import main as main_mod
    from app.services import chat_service as cs

    def broken(self, message, history=None):
        yield {"type": "sources", "sources": []}
        raise RuntimeError("boom")

    monkeypatch.setattr(cs.ChatService, "stream_answer", broken)
    client = TestClient(main_mod.app)
    with client.stream("POST", "/api/chat/stream",
                       json={"message": "hi", "history": []}) as resp:
        events = [json.loads(line[6:]) for line in resp.iter_lines()
                  if line.startswith("data: ")]
    assert events[-1]["type"] == "error"
```

- [ ] **Step 2: Run to verify failure** — 404 (no /stream route).

- [ ] **Step 3: Implement**

Router addition in `app/routers/chat.py`:
```python
import json

from fastapi.responses import StreamingResponse


@router.post("/stream")
def ask_stream(
    payload: ChatRequest,
    service: ChatService = Depends(get_chat_service),
):
    """SSE stream: sources first, then answer tokens, then done."""
    def sse():
        try:
            for event in service.stream_answer(payload.message,
                                               payload.history):
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
        except Exception as exc:  # noqa: BLE001 - stream must end cleanly
            yield ("data: " + json.dumps(
                {"type": "error", "message": str(exc)}) + "\n\n")

    return StreamingResponse(sse(), media_type="text/event-stream")
```
`ChatService.stream_answer`: reuse the existing `answer` flow's retrieval (read `chat_service.py`: `_retrieval_query`, retriever call, confidence gate, `_sources_from`); yield the sources event first; then produce tokens per the Streaming rule above; end with done. The refusal path yields the refusal message as a single token then done.

- [ ] **Step 4: Tests green + backend gauntlet.**

- [ ] **Step 5: Commit** — `git commit -m "feat: SSE streaming chat endpoint"`.

---

### Task 9: Frontend — bell, notification center, follow buttons

**Files:**
- Create: `ResearchSense/frontend/src/api/engagement.ts`
- Modify: `ResearchSense/frontend/src/layout/Header.tsx` (+ module.css) — bell with unread badge (signed-in faculty only)
- Create: `ResearchSense/frontend/src/components/NotificationBell.tsx` (+ module.css)
- Modify: `ResearchSense/frontend/src/pages/ResearcherProfile.tsx`, `ResearchSense/frontend/src/pages/Topics.tsx` (follow buttons)

**Interfaces:**
- Consumes Task 3 endpoints. API client (same authed-fetch idiom as `api/auth.ts` — read it first):
```ts
export interface NotificationItem {
  id: number; kind: string; text: string; read: boolean; created_at: string;
}
export interface Follows { kind: "researcher" | "topic" | "department"; target: string; }
export const fetchNotifications = () =>
  authedGet<{ unread: number; items: NotificationItem[] }>("/api/engagement/notifications");
export const markRead = (ids: number[]) =>
  authedPost("/api/engagement/notifications/read", { ids });
export const follow = (f: Follows) => authedPost("/api/engagement/follows", f);
export const unfollow = (f: Follows) => authedDelete("/api/engagement/follows", f);
export const fetchFollows = () => authedGet<Follows[]>("/api/engagement/follows");
```
(match the file's actual helper names).

- [ ] **Step 1: Build NotificationBell** — bell icon in the header, unread count badge (poll via react-query `refetchInterval: 60_000`), click opens a panel listing items (unread bold), "Mark all read" calls markRead with all unread ids and invalidates. Render only when a faculty token is present (reuse however Header/Portal detect the signed-in state — read first).
- [ ] **Step 2: Follow buttons** — ResearcherProfile: Follow/Unfollow button next to the name (state from fetchFollows); Topics page: per-topic follow toggle. Buttons render only for signed-in faculty; optimistic toggle + invalidate.
- [ ] **Step 3: Verify** — `npm run lint`, `npm run test`, `npm run build` all clean (full gauntlet). Add one vitest: `NotificationBell` renders unread badge from mocked fetchNotifications and calls markRead on "Mark all read" (mock the api module, wrap in QueryClientProvider — same pattern as Collaboration.test.tsx).
- [ ] **Step 4: Commit** — `git commit -m "feat: notification bell and follow buttons"`.

---

### Task 10: Frontend — dashboard cards (impact, recommendations, claims) + digest page

**Files:**
- Modify: `ResearchSense/frontend/src/features/portal/FacultyDashboard.tsx` (+ portal.module.css)
- Create: `ResearchSense/frontend/src/api/claims.ts`
- Modify: `ResearchSense/frontend/src/api/engagement.ts` (add `fetchDigest`)
- Modify: `ResearchSense/frontend/src/types/index.ts` (`bibliometrics`, `recommended_collaborators` on ResearcherDetail)

**Interfaces:**
- Consumes: researcher detail now carries `bibliometrics {h_index, i10, citations_total, citation_velocity, citations_by_year[]}` and `recommended_collaborators [{researcher_id, full_name, score, reasons[]}]`; `GET /api/claims/mine`, `POST /api/claims/accept|decline` {publication_key}; `GET /api/engagement/digest`.

- [ ] **Step 1: API clients** — `api/claims.ts` with `fetchMyClaims()`, `acceptClaim(key)`, `declineClaim(key)`; `fetchDigest()` in engagement.ts.
- [ ] **Step 2: "Your impact" card** — h-index / i10 / total citations / velocity as stat tiles + a small citations-by-year bar (reuse the existing Recharts patterns from `features/analytics/charts.tsx`; single hue; integer axes). Renders only when `bibliometrics` is non-empty.
- [ ] **Step 3: "People you could collaborate with" card** — top-5 `recommended_collaborators` with reason chips, each linking to the researcher profile. Empty → hide the card.
- [ ] **Step 4: "Papers that might be yours" card** — rows from fetchMyClaims with Accept / Not mine buttons; on action invalidate claims + profile queries; show the returned status message. Empty → hide.
- [ ] **Step 5: "Weekly digest" section** — render fetchDigest sections (new papers, updates, pending claims count, top recommendation, metrics) as a simple list card.
- [ ] **Step 6: Verify** — full gauntlet green; one vitest for the claims card (mocked api: renders rows; Accept calls acceptClaim with the key).
- [ ] **Step 7: Commit** — `git commit -m "feat: impact, recommendations, claims, digest on faculty dashboard"`.

---

### Task 11: Frontend — streaming chat client

**Files:**
- Modify: `ResearchSense/frontend/src/api/chat.ts` (add `streamChat`)
- Modify: `ResearchSense/frontend/src/features/chat/*` (read the folder first; wire progressive rendering into the existing message component)

**Interfaces:**
- Consumes Task 8's SSE contract. Client (fetch + ReadableStream — EventSource can't POST):
```ts
export async function streamChat(
  message: string,
  history: ChatTurn[],
  handlers: {
    onSources: (s: ChatSource[]) => void;
    onToken: (text: string) => void;
    onDone: () => void;
    onError: (msg: string) => void;
  },
): Promise<void> {
  const resp = await fetch("/api/chat/stream", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, history }),
  });
  if (!resp.ok || !resp.body) throw new Error(`HTTP ${resp.status}`);
  const reader = resp.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    let idx;
    while ((idx = buffer.indexOf("\n\n")) >= 0) {
      const line = buffer.slice(0, idx).trim();
      buffer = buffer.slice(idx + 2);
      if (!line.startsWith("data: ")) continue;
      const event = JSON.parse(line.slice(6));
      if (event.type === "sources") handlers.onSources(event.sources);
      else if (event.type === "token") handlers.onToken(event.text);
      else if (event.type === "done") handlers.onDone();
      else if (event.type === "error") handlers.onError(event.message);
    }
  }
}
```
- Chat UI: on send, append an empty assistant message and grow it per token; sources chip appears when `onSources` fires; on `onError` OR a thrown fetch error, fall back to the existing non-streaming `askChat` call and replace the message.
- [ ] **Steps:** read the chat feature folder → implement → full gauntlet green (one vitest for the SSE line-parser if extracted as a pure function — extract `parseSseChunk(buffer) -> {events, rest}` to make it testable) → `git commit -m "feat: streaming chat with graceful fallback"`.

---

### Task 12: RAG eval harness + QA docs

**Files:**
- Create: `ResearchSense/backend/eval/golden.json`
- Create: `ResearchSense/backend/scripts/rag_eval.py`
- Create: `ResearchSense/backend/tests/test_rag_eval.py`
- Modify: `docs/QA.md` (RAG evaluation section)
- Modify: `.gitignore` (add `ResearchSense/backend/eval/results-*.json`)

**Interfaces:**
- `golden.json`: `{"floor_hit5": 0.7, "questions": [{"question": str, "expected_labels": [str], "expected_kind": str}]}` — ~30 questions written against the CURRENT corpus (inspect `app/data/rag_chunks.json` labels to author them; researcher names, paper titles, topics).
- `scripts/rag_eval.py`: `evaluate(questions, retrieve) -> dict` (pure: hit@1, hit@5, mrr overall + per expected_kind; `retrieve(q) -> list[{"label": str, "kind": str}]`); `main()` wires the real Retriever, prints a table, writes `eval/results-<YYYY-MM-DD>.json`, exits 1 when hit@5 < floor. `--judge N` flag: sample N questions, run the full chat answer, ask Groq (via the existing agentic client utilities) to grade groundedness and relevance 1-5 with a fixed rubric prompt, print means — requires GROQ_API_KEY; refuses politely when absent.

- [ ] **Step 1: Write the failing test**

`tests/test_rag_eval.py`:
```python
from scripts.rag_eval import evaluate

QS = [{"question": "q1", "expected_labels": ["Paper: Alpha"],
       "expected_kind": "paper"},
      {"question": "q2", "expected_labels": ["Beta"],
       "expected_kind": "publication"}]


def fake_retrieve(question):
    if question == "q1":
        return [{"label": "Paper: Alpha (2024)", "kind": "paper"},
                {"label": "x", "kind": "paper"}]
    return [{"label": "x", "kind": "publication"},
            {"label": "y", "kind": "publication"},
            {"label": "Beta venue (2020)", "kind": "publication"}]


def test_metrics():
    m = evaluate(QS, fake_retrieve)
    assert m["hit_at_1"] == 0.5      # q1 rank1, q2 rank3
    assert m["hit_at_5"] == 1.0
    assert abs(m["mrr"] - (1.0 + 1 / 3) / 2) < 1e-9
    assert m["per_kind"]["paper"]["hit_at_5"] == 1.0


def test_miss_scores_zero():
    m = evaluate([{"question": "q", "expected_labels": ["nope"],
                   "expected_kind": "paper"}], lambda q: [])
    assert m["hit_at_5"] == 0.0 and m["mrr"] == 0.0
```

- [ ] **Step 2: Run to verify failure.**

- [ ] **Step 3: Implement `scripts/rag_eval.py`** — `evaluate` matches a question when any retrieved row's label contains any expected label substring (case-insensitive); rank = first matching row (1-based); hit@k / MRR standard. `main()`: load golden.json, build `retrieve` from `app.services.rag.retriever.Retriever` (top-5, mapping ScoredChunk → {"label", "kind"}), print, write artifact, exit per floor. `--judge N` implemented per the interface note; keep the rubric prompt a module constant.

- [ ] **Step 4: Author `eval/golden.json`** — 30 questions from the live corpus (e.g. "Who works on <topic X>?", "What is <paper title> about?", "Which campus has the most publications?" style — expected labels copied from actual `rag_chunks.json` labels). This file IS committed (it's source, not generated data).

- [ ] **Step 5: QA.md section** — when to run (`after any pipeline/index change`), commands, artifact location, floor semantics, updating golden.json after data refreshes, `--judge` usage + GROQ_API_KEY note.

- [ ] **Step 6: Tests green + backend gauntlet; run `python -m scripts.rag_eval` once for real and report the numbers.**

- [ ] **Step 7: Commit** — `git add eval/golden.json scripts/rag_eval.py tests/test_rag_eval.py ../../docs/QA.md ../../.gitignore` (adjust paths from backend cwd) → `git commit -m "feat: RAG evaluation harness with retrieval metrics and optional LLM judge"`.

---

### Task 13: BDD scenarios — follow→notify and claim→accept

**Files:**
- Create: `ResearchSense/backend/tests/features/engagement.feature`
- Create: `ResearchSense/backend/tests/steps/test_engagement_steps.py`

**Interfaces:**
- Consumes: the gauntlet's pytest-bdd conventions (`tests/features/*.feature` + `tests/steps/`), Task 1 store methods, Task 2 `fanout`, Task 6 `claims_service` (monkeypatch `_candidates`, `_append_fact_card`, `_clear_caches`, `PUBS_PATH`, `RESEARCHERS_PATH` exactly as `tests/test_claims.py` does).

- [ ] **Step 1: Write the feature file**

`tests/features/engagement.feature`:
```gherkin
Feature: Faculty engagement loop
  Follows produce notifications; claim candidates become confirmed papers.

  Scenario: A follower is notified about a followed researcher's new paper
    Given a faculty member following researcher 7
    When a publication_added event for researcher 7 is fanned out
    Then the follower has 1 unread notification mentioning the paper

  Scenario: Accepting a claim links the paper to the researcher
    Given a pending claim candidate for the signed-in researcher
    When they accept the claim
    Then the publication lists them as an author
    And the claim no longer appears as pending
```

- [ ] **Step 2: Write the step definitions**

`tests/steps/test_engagement_steps.py`:
```python
import json

import pytest
from pytest_bdd import given, scenarios, then, when

import app.repositories.accounts as accounts_mod
import app.services.claims_service as claims_svc
from app.repositories.accounts import AccountStore
from app.services.engagement import fanout, notification_text

scenarios("../features/engagement.feature")


@pytest.fixture()
def store(tmp_path, monkeypatch):
    monkeypatch.setattr(accounts_mod, "DB_PATH", tmp_path / "bdd.db")
    AccountStore._instance = None
    yield AccountStore.instance()
    AccountStore._instance = None


@given("a faculty member following researcher 7", target_fixture="follower")
def follower(store):
    store.create_account("0000-2", 9, "x")
    store.add_follow("0000-2", "researcher", "7")
    return "0000-2"


@when("a publication_added event for researcher 7 is fanned out")
def fan(store, follower):
    eid = store.append_event("publication_added", 7, {
        "title": "Fog Survey", "topics": [], "department": "",
        "author_ids": [7]})
    events = store.events_since("2000-01-01T00:00:00")
    pairs = fanout(events, store.all_follows(),
                   [{"orcid_id": "0000-2", "researcher_id": 9}])
    store.insert_notifications(pairs)


@then("the follower has 1 unread notification mentioning the paper")
def notified(store, follower):
    assert store.unread_count(follower) == 1
    rows = store.notifications_for(follower)
    assert "Fog Survey" in notification_text(rows[0])


@given("a pending claim candidate for the signed-in researcher",
       target_fixture="claim_ctx")
def claim_ctx(store, tmp_path, monkeypatch):
    cands = [{"researcher_id": 7, "publication_key": "doi:10.1/a",
              "title": "A", "journal_name": "J", "publication_year": 2024,
              "doi": "10.1/a"}]
    monkeypatch.setattr(claims_svc, "_candidates", lambda: cands)
    pubs_path = tmp_path / "pubs.json"
    pubs_path.write_text(json.dumps([{
        "publication_id": 1, "title": "A", "doi": "10.1/a",
        "publication_year": 2024, "journal_name": "J",
        "publication_type": "journal", "citation_count": 0, "campus": "K",
        "authors": [{"researcher_id": None, "full_name": "S Khan",
                     "order": 1}], "topics": []}]), "utf-8")
    rs_path = tmp_path / "rs.json"
    rs_path.write_text(json.dumps([{
        "researcher_id": 7, "full_name": "Sana Khan",
        "publication_count": 0, "citation_count": 0}]), "utf-8")
    monkeypatch.setattr(claims_svc, "PUBS_PATH", pubs_path)
    monkeypatch.setattr(claims_svc, "RESEARCHERS_PATH", rs_path)
    monkeypatch.setattr(claims_svc, "_append_fact_card", lambda record: None)
    monkeypatch.setattr(claims_svc, "_clear_caches", lambda: None)
    return {"pubs_path": pubs_path, "orcid": "0000-1", "rid": 7}


@when("they accept the claim")
def accept(claim_ctx):
    claims_svc.accept(claim_ctx["orcid"], claim_ctx["rid"], "doi:10.1/a")


@then("the publication lists them as an author")
def linked(claim_ctx):
    pubs = json.loads(claim_ctx["pubs_path"].read_text("utf-8"))
    assert pubs[0]["authors"][0]["researcher_id"] == 7


@then("the claim no longer appears as pending")
def not_pending(claim_ctx):
    assert claims_svc.pending_for(claim_ctx["rid"], claim_ctx["orcid"]) == []
```

- [ ] **Step 3: Run the scenarios + full backend gauntlet** — `pytest tests/steps/test_engagement_steps.py -v` PASS; `python -m scripts.gauntlet --backend-only` PASS.

- [ ] **Step 4: Commit** — `git commit -m "test: BDD scenarios for follow-notify and claim-accept"`.
