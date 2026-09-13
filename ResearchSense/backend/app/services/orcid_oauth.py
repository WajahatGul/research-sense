"""Sign in with ORCID: proof that an iD belongs to the person claiming it.

The registry check in ``orcid_service`` can only confirm that the name on a
public ORCID record matches the profile being claimed. ORCID iDs are public and
easy to look up, so that catches a mistake but not a deliberate impersonation —
and the roster is full of near-identical names.

Signing in at orcid.org settles it: ORCID authenticates the person and hands
back the iD it issued them, so the iD is theirs by construction.

The flow, and why it is shaped this way:

1. The researcher picks their profile and a password, then presses "Verify with
   ORCID". Those are held here against a one-time ``state`` value — never sent
   through the browser's URL, where they would end up in history and logs.
2. They are sent to ORCID and sign in there. We never see their password.
3. ORCID returns to the callback with a code; we exchange it server-side (the
   client secret never reaches the browser) and receive the authenticated iD.
4. The pending claim is completed and the browser is handed a session token.

Unconfigured, ``available()`` is False and the portal falls back to the name
check, saying plainly that is what it is doing.
"""

from __future__ import annotations

import secrets
import time
from dataclasses import dataclass

import httpx

from app.core.config import settings

#: A claim must be finished promptly; an abandoned one must not linger.
PENDING_TTL_SECONDS = 10 * 60


def available() -> bool:
    """True when an ORCID API client is configured."""
    return bool(settings.orcid_client_id and settings.orcid_client_secret)


def _base() -> str:
    return (
        "https://sandbox.orcid.org" if settings.orcid_sandbox else "https://orcid.org"
    )


@dataclass
class PendingClaim:
    researcher_id: int
    password: str
    created_at: float


# state -> pending claim. In memory: single process, and a lost claim simply
# means pressing the button again. Moving to several workers means moving this
# into the database.
_pending: dict[str, PendingClaim] = {}


def _prune() -> None:
    cutoff = time.time() - PENDING_TTL_SECONDS
    for state in [s for s, c in _pending.items() if c.created_at < cutoff]:
        _pending.pop(state, None)


def begin(researcher_id: int, password: str) -> str:
    """Hold the claim and return the ORCID URL to send the browser to."""
    _prune()
    state = secrets.token_urlsafe(32)
    _pending[state] = PendingClaim(researcher_id, password, time.time())
    query = httpx.QueryParams(
        {
            "client_id": settings.orcid_client_id,
            "response_type": "code",
            # The narrowest scope there is: authenticate, read nothing.
            "scope": "/authenticate",
            "redirect_uri": settings.orcid_redirect_uri,
            "state": state,
        }
    )
    return f"{_base()}/oauth/authorize?{query}"


def take_pending(state: str) -> PendingClaim | None:
    """Consume a pending claim. One use only, so a replayed callback fails."""
    _prune()
    return _pending.pop(state, None)


def exchange(code: str) -> str:
    """Swap the callback code for the authenticated ORCID iD.

    Raises ValueError with a user-safe message on any failure.
    """
    try:
        resp = httpx.post(
            f"{_base()}/oauth/token",
            data={
                "client_id": settings.orcid_client_id,
                "client_secret": settings.orcid_client_secret,
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": settings.orcid_redirect_uri,
            },
            headers={"Accept": "application/json"},
            timeout=30,
        )
    except httpx.HTTPError as exc:
        raise ValueError("Could not reach ORCID to complete sign-in.") from exc

    if resp.status_code != 200:
        raise ValueError("ORCID did not accept the sign-in. Please try again.")
    orcid_id = (resp.json() or {}).get("orcid") or ""
    if not orcid_id:
        raise ValueError("ORCID did not return an iD for that sign-in.")
    return orcid_id


def reset() -> None:
    """Drop every pending claim (tests)."""
    _pending.clear()
