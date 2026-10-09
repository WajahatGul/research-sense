"""Invite your co-authors: each claimed profile brings in the next.

A researcher who has just claimed their profile is the best person to bring
in the people they publish with: they know them, and their name on the
invitation is what makes it read as more than a mailing. This lists their
directory co-authors who have not claimed a profile yet, most joint papers
first, with a link that opens the claim form already set to that profile.

Nothing is sent from here. The researcher's own mail program sends the
invitation (the public directory email is used as the address), so there is
no mail server to run and no message goes out that they did not write.
"""

from __future__ import annotations

from collections import Counter

from fastapi import APIRouter, Depends

from app.core.config import settings
from app.core.security import current_user
from app.repositories import loader
from app.repositories.accounts import AccountStore
from app.routers.papers import _submitting_researcher

router = APIRouter(prefix="/api/invitations", tags=["invitations"])

LIMIT = 12


@router.get("/coauthors")
def coauthors_to_invite(token_payload: dict = Depends(current_user)):
    me = _submitting_researcher(token_payload)
    rid = me["researcher_id"]
    joint: Counter = Counter()
    for p in loader.load("publications"):
        ids = {a.get("researcher_id") for a in p.get("authors", [])} - {None}
        if rid in ids:
            joint.update(ids - {rid})

    store = AccountStore.instance()
    claimed = store.claimed_researcher_ids()
    waiting = {c["researcher_id"] for c in store.pending_claims()}
    people = {r["researcher_id"]: r for r in loader.load("researchers")}
    origin = settings.frontend_origin.rstrip("/")
    out = []
    for other, n in joint.most_common():
        r = people.get(other)
        if r is None or loader.is_extended(r) or other in claimed or other in waiting:
            continue
        out.append(
            {
                "researcher_id": other,
                "full_name": r["full_name"],
                "department": r.get("department") or "",
                "email": r.get("email") or None,
                "joint_papers": n,
                "claim_link": f"{origin}/portal?claim={other}",
            }
        )
        if len(out) == LIMIT:
            break
    return {"inviter": me["full_name"], "coauthors": out}
