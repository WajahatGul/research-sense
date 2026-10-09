"""Saved searches that email when something new matches.

Someone looking for work on a subject (a student choosing a supervisor, a
company looking for expertise, a researcher following a field) had to come
back and search again to see what was new. Now they can keep a search: any
search or filter on Publications or Researchers, with their email. After
each data refresh and each paper an admin approves, every kept search is
run again, and new matches are sent in one short message.

An alert starts only when the address confirms it (the link in the first
message), so nobody can sign someone else up; every message carries a link
to stop it. Only the items a search had not already shown are sent.
"""

from __future__ import annotations

import json
import logging
import re
import secrets
import threading
from datetime import UTC, datetime

from app.core.config import settings
from app.core.deps import get_publication_service, get_researcher_service
from app.repositories.accounts import AccountStore
from app.services import notify_service

log = logging.getLogger("researchsense.alerts")

# The filters each list accepts, as the API names them.
FILTERS = {
    "publications": (
        "q",
        "year",
        "campus",
        "department",
        "publication_type",
        "date_from",
        "date_to",
        "topic_id",
    ),
    "researchers": ("q", "campus", "department", "designation", "topic_id"),
}
INTEGER = {"year", "topic_id"}
EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
MAX_PER_EMAIL = 10
MAX_UNCONFIRMED = 3
MAX_ITEMS_PER_MESSAGE = 10
_lock = threading.Lock()


class AlertError(ValueError):
    """The alert cannot be kept as asked."""


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _clean(kind: str, filters: dict) -> dict:
    if kind not in FILTERS:
        raise AlertError("Alerts can follow publications or researchers.")
    out = {}
    for key, value in filters.items():
        if key not in FILTERS[kind]:
            raise AlertError(f"Unknown filter: {key}")
        if value in (None, ""):
            continue
        if key in INTEGER:
            try:
                value = int(value)
            except (TypeError, ValueError) as exc:
                raise AlertError(f"{key} must be a number") from exc
        else:
            value = " ".join(str(value).split())[:200]
        out[key] = value
    if not out:
        raise AlertError(
            "Search or choose a filter first: an alert on everything would never stop."
        )
    return out


def matches(kind: str, filters: dict) -> list[dict]:
    """Everything the saved search finds now, as {id, title, detail}."""
    args = {("query" if k == "q" else k): v for k, v in filters.items()}
    if kind == "publications":
        page = get_publication_service().list(**args, page=1, page_size=100_000)
        return [
            {
                "id": p.publication_id,
                "title": p.title,
                "detail": ", ".join(
                    filter(None, [p.journal_name, str(p.publication_year or "")])
                ),
            }
            for p in page.items
        ]
    page = get_researcher_service().list(**args, page=1, page_size=100_000)
    return [
        {
            "id": r.researcher_id,
            "title": r.full_name,
            "detail": ", ".join(filter(None, [r.designation, r.department])),
        }
        for r in page.items
    ]


def describe(kind: str, filters: dict) -> str:
    """The search in words, for the messages.

    For example: “machine learning”, 2024 in publications.
    """
    parts = [f"“{filters['q']}”"] if filters.get("q") else []
    parts += [str(v) for k, v in filters.items() if k not in ("q", "topic_id")]
    if filters.get("topic_id"):
        parts.append("one research area")
    return f"{', '.join(parts)} in {kind}"


def _site() -> str:
    return settings.frontend_origin.rstrip("/")


def _links(token: str) -> tuple[str, str]:
    return f"{_site()}/alerts?confirm={token}", f"{_site()}/alerts?stop={token}"


def create(email: str, kind: str, filters: dict) -> dict:
    email = email.strip().lower()
    if not EMAIL.match(email) or len(email) > 200:
        raise AlertError("Enter a valid email address.")
    filters = _clean(kind, filters)
    filters_json = json.dumps(filters, sort_keys=True)
    with AccountStore.instance()._connect() as con:
        existing = con.execute(
            "SELECT * FROM saved_searches"
            " WHERE email = ? AND kind = ? AND filters_json = ?"
            " AND stopped = 0",
            (email, kind, filters_json),
        ).fetchone()
        if existing and existing["confirmed"]:
            return {"status": "already on"}
        mine = con.execute(
            "SELECT confirmed, COUNT(*) AS n FROM saved_searches"
            " WHERE email = ? AND stopped = 0"
            " GROUP BY confirmed",
            (email,),
        ).fetchall()
        counts = {row["confirmed"]: row["n"] for row in mine}
        if not existing:
            if sum(counts.values()) >= MAX_PER_EMAIL:
                raise AlertError(f"An address can keep up to {MAX_PER_EMAIL} alerts.")
            if counts.get(0, 0) >= MAX_UNCONFIRMED:
                raise AlertError(
                    "Confirm the alerts already sent to this address first."
                )
    # What it finds today is not news: only later matches are sent.
    seen = [m["id"] for m in matches(kind, filters)]
    token = existing["token"] if existing else secrets.token_urlsafe(24)
    if not existing:
        with AccountStore.instance()._connect() as con:
            con.execute(
                "INSERT INTO saved_searches (email, kind, filters_json,"
                " token, seen_json,"
                " created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (email, kind, filters_json, token, json.dumps(seen), _now()),
            )
    confirm, stop = _links(token)
    notify_service.send(
        email,
        "Confirm your ResearchSense alert",
        "You asked to hear when something new matches this search on ResearchSense:\n\n"
        f"  {describe(kind, filters)}\n\n"
        f"Confirm it here, and we will write only when there is"
        f" something new:\n\n{confirm}\n\n"
        "If you did not ask for this, ignore this message: nothing will be sent.\n\n"
        f"Stop it at any time: {stop}",
        "alert confirmation",
    )
    return {"status": "check your email"}


def _by_token(token: str):
    with AccountStore.instance()._connect() as con:
        return con.execute(
            "SELECT * FROM saved_searches WHERE token = ?", (token or "",)
        ).fetchone()


def confirm(token: str) -> dict:
    row = _by_token(token)
    if row is None or row["stopped"]:
        raise AlertError("This alert link is not valid any more.")
    with AccountStore.instance()._connect() as con:
        con.execute(
            "UPDATE saved_searches SET confirmed = 1 WHERE id = ?", (row["id"],)
        )
    return {
        "status": "confirmed",
        "search": describe(row["kind"], json.loads(row["filters_json"])),
    }


def stop(token: str) -> dict:
    row = _by_token(token)
    if row is None:
        raise AlertError("This alert link is not valid any more.")
    with AccountStore.instance()._connect() as con:
        con.execute("UPDATE saved_searches SET stopped = 1 WHERE id = ?", (row["id"],))
    return {
        "status": "stopped",
        "search": describe(row["kind"], json.loads(row["filters_json"])),
    }


def run_all() -> int:
    """Run every confirmed alert; email the new matches. Returns messages sent."""
    if not _lock.acquire(blocking=False):
        return 0  # already running; it will see the same data
    sent = 0
    try:
        with AccountStore.instance()._connect() as con:
            rows = con.execute(
                "SELECT * FROM saved_searches WHERE confirmed = 1 AND stopped = 0"
            ).fetchall()
        for row in rows:
            try:
                sent += _run_one(row)
            except Exception:  # noqa: BLE001 - one bad alert must not stop the rest
                log.exception("alert %s failed", row["id"])
    finally:
        _lock.release()
    return sent


def _run_one(row) -> int:
    kind, filters = row["kind"], json.loads(row["filters_json"])
    found = matches(kind, filters)
    seen = set(json.loads(row["seen_json"]))
    new = [m for m in found if m["id"] not in seen]
    if not new:
        return 0
    lines = []
    for m in new[:MAX_ITEMS_PER_MESSAGE]:
        detail = f" ({m['detail']})" if m["detail"] else ""
        lines.append(f"- {m['title']}{detail}\n  {_site()}/{kind}/{m['id']}")
    more = len(new) - MAX_ITEMS_PER_MESSAGE
    if more > 0:
        lines.append(f"…and {more} more.")
    _, stop_link = _links(row["token"])
    notify_service.send(
        row["email"],
        f"{len(new)} new on ResearchSense: {describe(kind, filters)}"[:150],
        f"New since we last wrote, for {describe(kind, filters)}:\n\n"
        + "\n".join(lines)
        + f"\n\nStop this alert: {stop_link}",
        f"alert {row['id']}",
    )
    with AccountStore.instance()._connect() as con:
        con.execute(
            "UPDATE saved_searches SET seen_json = ?, last_sent_at = ? WHERE id = ?",
            (json.dumps(sorted(seen | {m["id"] for m in found})), _now(), row["id"]),
        )
    return 1


def run_in_background() -> None:
    threading.Thread(target=run_all, daemon=True).start()
