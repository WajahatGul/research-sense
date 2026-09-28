"""Correcting who wrote what: researchers propose, administrators decide.

See app/services/identity_service.py for how decisions are kept and applied.
"""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.core.security import current_admin, current_user
from app.repositories import loader
from app.repositories.accounts import AccountStore
from app.routers.papers import _submitting_researcher
from app.services import identity_service

router = APIRouter(prefix="/api/corrections", tags=["corrections"])
admin = APIRouter(
    prefix="/api/admin/corrections",
    tags=["admin"],
    dependencies=[Depends(current_admin)],
)


class NotMine(BaseModel):
    publication_id: int
    note: str = Field("", max_length=500)


class SamePerson(BaseModel):
    openalex_id: str = Field(min_length=2, max_length=40)
    note: str = Field("", max_length=500)


class Decide(BaseModel):
    researcher_id: int
    openalex_id: str = Field(min_length=2, max_length=40)
    same: bool
    note: str = Field("", max_length=500)


class RejectBody(BaseModel):
    note: str | None = None


def _describe(c: dict) -> dict:
    payload = json.loads(c["payload_json"])
    return {
        "id": c["id"],
        "kind": c["kind"],
        "status": c["status"],
        "researcher_id": c["researcher_id"],
        "profile_name": payload["profile"]["name"],
        "paper_title": (payload.get("paper") or {}).get("title"),
        "paper_doi": (payload.get("paper") or {}).get("doi"),
        "other_name": (payload.get("other") or {}).get("name"),
        "other_openalex_id": (payload.get("other") or {}).get("openalex_id"),
        "note": c.get("note") or "",
        "raised_by": c["raised_by"],
        "submitted_at": c["submitted_at"],
        "review_note": c.get("review_note"),
    }


# --- researchers --------------------------------------------------------------

@router.get("/mine")
def my_corrections(token_payload: dict = Depends(current_user)):
    """What I have asked for, and author records that may also be me."""
    me = _submitting_researcher(token_payload)
    return {
        "corrections": [_describe(c) for c in
                        AccountStore.instance().corrections_for(me["researcher_id"])],
        "suggestions": identity_service.candidates(for_researcher=me["researcher_id"]),
    }


@router.post("/not-mine")
def not_mine(body: NotMine, token_payload: dict = Depends(current_user)):
    me = _submitting_researcher(token_payload)
    try:
        cid = identity_service.propose_not_author(me["researcher_id"], body.publication_id,
                                                  body.note)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"id": cid, "status": "pending",
            "message": "Sent for review. The paper stays on your profile until an "
                       "administrator removes it."}


@router.post("/same-person")
def same_person(body: SamePerson, token_payload: dict = Depends(current_user)):
    me = _submitting_researcher(token_payload)
    try:
        cid = identity_service.propose_same_person(me["researcher_id"], body.openalex_id,
                                                   body.note)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"id": cid, "status": "pending",
            "message": "Sent for review. Those papers join your profile once an "
                       "administrator confirms it."}


@router.post("/not-me")
def not_me(body: SamePerson, token_payload: dict = Depends(current_user)):
    """Dismiss a suggestion. Changes no data, so it needs no review."""
    me = _submitting_researcher(token_payload)
    identity_service.decide_different_people(me["researcher_id"], body.openalex_id,
                                             by="researcher")
    return {"status": "recorded"}


# --- administrators ------------------------------------------------------------

@admin.get("")
def pending():
    """Corrections researchers asked for, with what the record shows."""
    out = []
    pubs = loader.load("publications")
    for c in AccountStore.instance().pending_corrections():
        row = _describe(c)
        if c["kind"] == "same_person":
            match = next((x for x in identity_service.candidates(
                for_researcher=c["researcher_id"], limit=500, include_waiting=True)
                if x["openalex_id"] == row["other_openalex_id"]), None)
            row["evidence"] = match
        else:
            paper = next((p for p in pubs if (p.get("doi") or "").lower() == (row["paper_doi"] or "")
                          or p["title"] == row["paper_title"]), None)
            row["evidence"] = {
                "printed_names": [a["full_name"] for a in (paper or {}).get("authors", [])],
                "journal": (paper or {}).get("journal_name"),
                "year": (paper or {}).get("publication_year"),
            }
        out.append(row)
    return out


def _audit(who: dict, action: str, target: str, detail: str = "") -> None:
    AccountStore.instance().record(who.get("sub", "?"), action, target, detail)


@admin.post("/{correction_id}/approve")
def approve(correction_id: int, who: dict = Depends(current_admin)):
    try:
        d = identity_service.approve_correction(correction_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    _audit(who, "correction.approved", f"correction {correction_id}",
           f"{d['type']}: {d['profile']['name']}")
    return {"status": "approved"}


@admin.post("/{correction_id}/reject")
def reject(correction_id: int, body: RejectBody, who: dict = Depends(current_admin)):
    try:
        identity_service.reject_correction(correction_id, body.note)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    _audit(who, "correction.rejected", f"correction {correction_id}", body.note or "")
    return {"status": "rejected"}


@admin.get("/candidates")
def possible_duplicates(limit: int = 30):
    """Author records that may be a directory person, strongest evidence first."""
    return identity_service.candidates(limit=min(limit, 200))


@admin.post("/candidates/decide")
def decide(body: Decide, who: dict = Depends(current_admin)):
    if body.same:
        identity_service.decide_same_person(body.researcher_id, body.openalex_id,
                                            by="admin", note=body.note)
    else:
        identity_service.decide_different_people(body.researcher_id, body.openalex_id,
                                                 by="admin")
    _audit(who, "identity.same_person" if body.same else "identity.different_people",
           f"researcher {body.researcher_id}", body.openalex_id)
    return {"status": "recorded"}
