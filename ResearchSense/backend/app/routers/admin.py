"""Admin endpoints: claimed accounts, activation, and data refresh."""

from __future__ import annotations

import asyncio
import json
import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.core.deps import get_researcher_service
from app.core.security import current_admin
from app.repositories.accounts import AccountStore
from app.schemas.auth import ClaimedAccount
from app.services import refresh_service, staging, submission_service

log = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/admin", tags=["admin"], dependencies=[Depends(current_admin)]
)


class RejectBody(BaseModel):
    note: str | None = None


@router.get("/accounts", response_model=list[ClaimedAccount])
def list_accounts():
    service = get_researcher_service()
    out = []
    for account in AccountStore.instance().list_accounts():
        researcher = service.get(account["researcher_id"])
        out.append(
            ClaimedAccount(
                orcid_id=account["orcid_id"],
                researcher_id=account["researcher_id"],
                full_name=researcher.full_name if researcher else "(unknown)",
                active=bool(account["active"]),
                created_at=account["created_at"],
            )
        )
    return out


@router.post("/accounts/{orcid_id}/active")
def set_account_active(orcid_id: str, active: bool):
    AccountStore.instance().set_active(orcid_id, active)
    return {"orcid_id": orcid_id, "active": active}


@router.get("/refresh")
def refresh_status():
    last = AccountStore.instance().last_refresh()
    return {"last_refresh": last, "due": refresh_service.is_due()}


@router.post("/refresh")
async def trigger_refresh():
    """Start a data refresh in the background; check GET /refresh for status."""
    asyncio.get_running_loop().run_in_executor(None, refresh_service.run_refresh)
    return {"status": "started"}


@router.get("/papers/pending")
def pending_papers():
    """Papers awaiting review, oldest first, with the full record payload."""
    out = []
    for s in AccountStore.instance().pending_submissions():
        out.append(
            {
                "id": s["id"],
                "kind": s["kind"],
                "researcher_id": s["researcher_id"],
                "title": s["title"],
                "submitted_at": s["submitted_at"],
                "record": json.loads(s["record_json"]),
            }
        )
    return out


@router.post("/papers/{sub_id}/approve")
def approve_paper(sub_id: int):
    """Publish a pending paper and merge its staged chunks (instant go-live).
    Idempotent: an already-approved paper is a no-op. A rejected submission
    can never be approved — its staged vectors were discarded on rejection,
    so publishing it would create a record with no searchable chunk."""
    store = AccountStore.instance()
    sub = store.get_submission(sub_id)
    if sub is None:
        raise HTTPException(status_code=404, detail="No such submission")
    if sub["status"] == "approved":
        return {"status": "approved", "id": sub_id, "chunks_merged": 0}
    if sub["status"] == "rejected":
        raise HTTPException(
            status_code=409,
            detail="This submission was rejected; it cannot be approved.",
        )
    if sub["kind"] == "publication":
        submission_service.publish_record(json.loads(sub["record_json"]))
    merged = staging.merge_staged(sub_id)
    if merged == 0 and sub["kind"] in ("publication", "upload"):
        log.warning(
            "Approval of submission %s (kind=%s) merged 0 staged chunks — "
            "it will not be searchable via the chatbot until re-indexed.",
            sub_id,
            sub["kind"],
        )
    store.set_submission_status(sub_id, "approved")
    return {"status": "approved", "id": sub_id, "chunks_merged": merged}


@router.post("/papers/{sub_id}/reject")
def reject_paper(sub_id: int, body: RejectBody):
    """Reject a pending paper; its staged chunks are discarded. For a PDF
    upload, also deletes the uploaded file and its uploads-table row so a
    rejected paper can never be picked up by a full index rebuild."""
    store = AccountStore.instance()
    sub = store.get_submission(sub_id)
    if sub is None:
        raise HTTPException(status_code=404, detail="No such submission")
    staging.discard_staged(sub_id)
    if sub["kind"] == "upload":
        from app.routers.papers import UPLOADS_DIR

        filename = json.loads(sub["record_json"]).get("filename")
        if filename:
            (UPLOADS_DIR / filename).unlink(missing_ok=True)
        store.delete_upload_for_submission(sub_id)
    store.set_submission_status(sub_id, "rejected", note=body.note)
    return {"status": "rejected", "id": sub_id}
