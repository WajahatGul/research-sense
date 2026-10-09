"""Tell people what was decided about them.

A researcher who claimed a profile, sent in a paper or asked for a
correction used to hear nothing: they had to come back and look. Each
decision now sends a short email saying what was decided and what to do
next, to the address in the directory. For a claim that is deliberate: if
someone else claimed the profile, its real owner hears about it.

Every message is written to the outbox first. With a mail server set
(SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, SMTP_FROM) it is then
sent; without one it stays in the outbox marked "not sent", where an admin
can read it and pass it on. Sending never holds up or undoes a decision.
"""

from __future__ import annotations

import json
import logging
import os
import smtplib
import threading
from datetime import UTC, datetime
from email.message import EmailMessage

from app.core.config import settings
from app.repositories import loader
from app.repositories.accounts import AccountStore

log = logging.getLogger("researchsense.notify")

SENT, NOT_SENT, FAILED = "sent", "not sent", "failed"


def _smtp() -> dict | None:
    host = os.getenv("SMTP_HOST", "").strip()
    if not host:
        return None
    user = os.getenv("SMTP_USER", "").strip()
    return {
        "host": host,
        "port": int(os.getenv("SMTP_PORT", "587")),
        "user": user,
        "password": os.getenv("SMTP_PASSWORD", ""),
        "sender": os.getenv("SMTP_FROM", "").strip() or user,
    }


def researcher(researcher_id: int) -> dict | None:
    return next(
        (r for r in loader.load("researchers") if r["researcher_id"] == researcher_id),
        None,
    )


def _portal() -> str:
    return f"{settings.frontend_origin.rstrip('/')}/portal"


def _deliver(outbox_id: int, config: dict, message: EmailMessage) -> None:
    status, error = SENT, None
    try:
        with smtplib.SMTP(config["host"], config["port"], timeout=20) as smtp:
            smtp.starttls()
            if config["user"]:
                smtp.login(config["user"], config["password"])
            smtp.send_message(message)
    except Exception as exc:  # noqa: BLE001 - recorded, never raised
        status, error = FAILED, str(exc)[:300]
        log.warning("notify: sending message %s failed: %s", outbox_id, exc)
    with AccountStore.instance()._connect() as con:
        con.execute(
            "UPDATE outbox SET status = ?, error = ? WHERE id = ?",
            (status, error, outbox_id),
        )


def send(to: str | None, subject: str, body: str, reason: str) -> int | None:
    """Record a message and send it if a mail server is set. Never raises."""
    if not to:
        log.info("notify: no address for %s", reason)
        return None
    config = _smtp()
    try:
        with AccountStore.instance()._connect() as con:
            cur = con.execute(
                "INSERT INTO outbox (at, to_addr, subject, body, reason, status)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                (
                    datetime.now(UTC).isoformat(timespec="seconds"),
                    to,
                    subject,
                    body,
                    reason,
                    "sending" if config else NOT_SENT,
                ),
            )
            outbox_id = int(cur.lastrowid)
    except Exception:  # noqa: BLE001 - a decision must not fail over a message
        log.exception("notify: could not record message")
        return None
    if config:
        message = EmailMessage()
        message["From"], message["To"], message["Subject"] = (
            config["sender"],
            to,
            subject,
        )
        message.set_content(body)
        threading.Thread(
            target=_deliver, args=(outbox_id, config, message), daemon=True
        ).start()
    return outbox_id


def recent(limit: int = 30) -> list[dict]:
    with AccountStore.instance()._connect() as con:
        rows = con.execute(
            "SELECT * FROM outbox ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
    return [dict(r) for r in rows]


def _letter(person: dict, text: str) -> str:
    org = f" · {settings.institution_name}" if settings.institution_name else ""
    return (
        f"Dear {person.get('full_name', 'colleague')},\n\n{text}\n\nResearchSense{org}"
    )


def _note(note: str | None) -> str:
    return f"\n\nThe reviewer's note: {note}" if note else ""


# --- the decisions ---------------------------------------------------------


def claim_decided(claim: dict, approved: bool, note: str | None = None) -> None:
    person = researcher(claim["researcher_id"])
    if person is None:
        return
    if approved:
        subject = "Your ResearchSense profile is yours"
        text = (
            "The claim on your profile has been approved. You can now sign in to "
            "correct your record, add missing papers and keep your details current:\n\n"
            f"{_portal()}\n\n"
            "If you did not claim this profile, reply to this message straight away."
        )
    else:
        subject = "About the claim on your ResearchSense profile"
        text = (
            "A claim on your profile was not approved." + _note(note) + "\n\n"
            "If it was yours, you can claim again, ideally by signing in with ORCID, "
            f"which proves the iD is yours:\n\n{_portal()}"
        )
    send(
        person.get("email"),
        subject,
        _letter(person, text),
        f"claim {claim['id']} {'approved' if approved else 'rejected'}",
    )


def paper_decided(submission: dict, approved: bool, note: str | None = None) -> None:
    person = researcher(submission["researcher_id"])
    if person is None:
        return
    title = submission["title"]
    if approved:
        subject = "Your paper is on ResearchSense"
        text = (
            f"“{title}” has been approved and now appears on your"
            " profile and in search."
        )
    else:
        subject = "About the paper you sent to ResearchSense"
        text = (
            f"“{title}” was not added."
            + _note(note)
            + f"\n\nYou can send a corrected version from your portal:\n\n{_portal()}"
        )
    send(
        person.get("email"),
        subject,
        _letter(person, text),
        f"paper {submission['id']} {'approved' if approved else 'rejected'}",
    )


_CORRECTION = {
    "not_author": "that a paper listed on your profile is not yours",
    "same_person": "that another author record is also you",
}


def correction_decided(
    correction: dict, approved: bool, note: str | None = None
) -> None:
    person = researcher(correction["researcher_id"])
    if person is None:
        return
    try:
        payload = json.loads(correction.get("payload_json") or "{}")
    except ValueError:
        payload = {}
    paper = payload.get("paper")
    other = payload.get("other")
    title = paper.get("title") if isinstance(paper, dict) else None
    name = other.get("name") if isinstance(other, dict) else None
    detail = f" (“{title}”)" if title else f" ({name})" if name else ""
    what = _CORRECTION.get(correction["kind"], "about a correction to your record")
    if approved:
        subject = "Your record has been corrected"
        text = f"You told us {what}{detail}. We agreed, and your profile now shows it."
    else:
        subject = "About the correction you asked for"
        text = (
            f"You told us {what}{detail}. We have kept the record as it was."
            + _note(note)
        )
    send(
        person.get("email"),
        subject,
        _letter(person, text),
        f"correction {correction['id']} {'approved' if approved else 'rejected'}",
    )
