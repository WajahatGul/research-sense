"""What people do on the site, in the few numbers that say whether it works.

Three questions, each tied to a decision:

- Which searches find nothing? Each is a researcher, a paper or a word for
  an area that the directory is missing, or a spelling it should accept.
- How many people start claiming their profile, and how many finish? A gap
  means the claim form is losing them.
- Do visitors come back? A directory people return to is one they trust.

Nothing identifies a person. A visitor is a random id the browser made up
and keeps; there are no IPs, cookies or accounts in these rows. A visit is
counted once per visitor per day, and a claim started once per visitor per
profile.
"""

from __future__ import annotations

import re
from collections import Counter
from datetime import UTC, datetime, timedelta

from app.repositories.accounts import AccountStore

# Events a browser may report; searches are recorded by the server itself.
CLIENT_KINDS = ("visit", "claim_started")
VISITOR = re.compile(r"^[A-Za-z0-9-]{8,64}$")
KEEP_DAYS = 400


def _today() -> str:
    return datetime.now(UTC).date().isoformat()


def record(kind: str, visitor: str = "", detail: str = "") -> bool:
    """Store one event; return False when it only repeats one already counted."""
    detail = detail.strip()[:120]
    day = _today()
    with AccountStore.instance()._connect() as con:
        if kind in CLIENT_KINDS:
            # A visit counts once a day; a claim started once per profile.
            where = "kind = ? AND visitor = ? AND detail = ?"
            args = [kind, visitor, detail]
            if kind == "visit":
                where += " AND day = ?"
                args.append(day)
            if con.execute(f"SELECT 1 FROM events WHERE {where} LIMIT 1", args).fetchone():
                return False
        con.execute(
            "INSERT INTO events (at, day, kind, visitor, detail) VALUES (?, ?, ?, ?, ?)",
            (datetime.now(UTC).isoformat(timespec="seconds"), day, kind, visitor, detail),
        )
        cutoff = (datetime.now(UTC) - timedelta(days=KEEP_DAYS)).date().isoformat()
        con.execute("DELETE FROM events WHERE day < ?", (cutoff,))
    return True


def search_found_nothing(where: str, query: str | None) -> None:
    """Called by the list endpoints when a typed search matched nothing."""
    q = " ".join((query or "").lower().split())
    if len(q) >= 3:
        record(f"search_empty:{where}", detail=q)


def summary(days: int = 30) -> dict:
    since_day = (datetime.now(UTC) - timedelta(days=days)).date().isoformat()
    since = f"{since_day}T00:00:00"
    with AccountStore.instance()._connect() as con:
        visits = con.execute(
            "SELECT visitor, COUNT(DISTINCT day) AS days FROM events"
            " WHERE kind = 'visit' AND day >= ? GROUP BY visitor",
            (since_day,),
        ).fetchall()
        empty = con.execute(
            "SELECT kind, detail FROM events WHERE kind LIKE 'search_empty:%' AND day >= ?",
            (since_day,),
        ).fetchall()
        started = con.execute(
            "SELECT COUNT(*) FROM events WHERE kind = 'claim_started' AND day >= ?",
            (since_day,),
        ).fetchone()[0]
        sent = con.execute(
            "SELECT COUNT(*) FROM claims WHERE submitted_at >= ?", (since,)
        ).fetchone()[0]
        opened = con.execute(
            "SELECT COUNT(*) FROM accounts WHERE created_at >= ?", (since,)
        ).fetchone()[0]
    misses = Counter((row["detail"], row["kind"].split(":", 1)[1]) for row in empty)
    return {
        "days": days,
        "visitors": len(visits),
        "returning_visitors": sum(1 for v in visits if v["days"] >= 2),
        "searches_without_results": sum(misses.values()),
        "top_missed_searches": [
            {"query": q, "where": w, "times": n} for (q, w), n in misses.most_common(15)
        ],
        "claims": {"started": started, "sent_for_review": sent, "profiles_claimed": opened},
    }
