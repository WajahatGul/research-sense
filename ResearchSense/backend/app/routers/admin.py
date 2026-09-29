"""Admin endpoints: claimed accounts, activation, and data refresh."""

from __future__ import annotations

import asyncio
import json
import logging
from collections import Counter

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.core.deps import get_auth_service, get_researcher_service
from app.core.security import current_admin
from app.repositories.accounts import AccountStore
from app.schemas.auth import ClaimedAccount, ClaimResult, PendingClaim
from app.services import admin_accounts, alerts_service, backup_service, notify_service, usage_service, refresh_service, staging, submission_service

log = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/admin", tags=["admin"], dependencies=[Depends(current_admin)]
)


class RejectBody(BaseModel):
    note: str | None = None


class NewAdmin(BaseModel):
    username: str = Field(min_length=3, max_length=40)
    password: str = Field(min_length=1, max_length=200)


class PasswordChange(BaseModel):
    current: str = Field(min_length=1, max_length=200)
    new: str = Field(min_length=1, max_length=200)


def _audit(admin: dict, action: str, target: str = "", detail: str = "") -> None:
    AccountStore.instance().record(admin.get("sub", "?"), action, target, detail)


# --- administrators and the activity log ----------------------------------------

@router.get("/admins")
def list_admins():
    return AccountStore.instance().list_admins()


@router.post("/admins")
def add_admin(body: NewAdmin, admin: dict = Depends(current_admin)):
    try:
        admin_accounts.add_admin(admin["sub"], body.username, body.password)
    except admin_accounts.AdminError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"status": "created"}


@router.post("/admins/{username}/active")
def set_admin_active(username: str, active: bool, admin: dict = Depends(current_admin)):
    try:
        admin_accounts.set_active(admin["sub"], username, active)
    except admin_accounts.AdminError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"username": username, "active": active}


@router.post("/password")
def change_password(body: PasswordChange, admin: dict = Depends(current_admin)):
    try:
        admin_accounts.change_password(admin["sub"], body.current, body.new)
    except admin_accounts.AdminError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"status": "changed"}


@router.get("/activity")
def activity(limit: int = 50):
    """Who did what, newest first. The log can be read, never edited."""
    return AccountStore.instance().recent_activity(min(max(limit, 1), 200))


@router.get("/claims", response_model=list[PendingClaim])
def pending_claims():
    """Profile claims waiting for a decision, with the evidence to judge by."""
    service = get_researcher_service()
    store = AccountStore.instance()
    rows = store.pending_claims()
    waiting_on = Counter(c["researcher_id"] for c in rows)
    out = []
    for c in rows:
        researcher = service.get(c["researcher_id"])
        evidence = json.loads(c.get("evidence_json") or "{}")
        out.append(
            PendingClaim(
                id=c["id"],
                orcid_id=c["orcid_id"],
                researcher_id=c["researcher_id"],
                profile_name=researcher.full_name if researcher else "(unknown)",
                profile_department=researcher.department if researcher else "",
                profile_campus=researcher.campus if researcher else "",
                orcid_names=evidence.get("orcid_names", []),
                orcid_employers=evidence.get("orcid_employers", []),
                submitted_at=c["submitted_at"],
                competing_claims=waiting_on[c["researcher_id"]] - 1,
                orcid_verified=bool(evidence.get("orcid_verified")),
            )
        )
    return out


@router.post("/claims/{claim_id}/approve", response_model=ClaimResult)
def approve_claim(claim_id: int, admin: dict = Depends(current_admin)):
    result = get_auth_service().approve_claim(claim_id)
    _audit(admin, "claim.approved", f"claim {claim_id}", result.full_name or "")
    notify_service.claim_decided(AccountStore.instance().get_claim(claim_id), approved=True)
    return result


@router.post("/claims/{claim_id}/reject")
def reject_claim(claim_id: int, body: RejectBody, admin: dict = Depends(current_admin)):
    get_auth_service().reject_claim(claim_id, body.note)
    _audit(admin, "claim.rejected", f"claim {claim_id}", body.note or "")
    notify_service.claim_decided(AccountStore.instance().get_claim(claim_id), False, body.note)
    return {"status": "rejected"}


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
def set_account_active(orcid_id: str, active: bool, admin: dict = Depends(current_admin)):
    AccountStore.instance().set_active(orcid_id, active)
    _audit(admin, "account.activated" if active else "account.deactivated", orcid_id)
    return {"orcid_id": orcid_id, "active": active}


@router.get("/refresh")
def refresh_status():
    last = AccountStore.instance().last_refresh()
    return {"last_refresh": last, "due": refresh_service.is_due()}


@router.post("/refresh")
async def trigger_refresh(admin: dict = Depends(current_admin)):
    """Start a data refresh in the background; check GET /refresh for status."""
    _audit(admin, "refresh.started")
    asyncio.get_running_loop().run_in_executor(None, refresh_service.run_refresh)
    return {"status": "started"}


@router.get("/outbox")
def outbox():
    return {"messages": notify_service.recent(), "mail_server": notify_service._smtp() is not None}


@router.post("/alerts/run")
def run_alerts(admin: dict = Depends(current_admin)):
    """Check every saved search now (it also runs after each refresh and approval)."""
    sent = alerts_service.run_all()
    _audit(admin, "alerts.run", "", f"{sent} sent")
    return {"sent": sent}


@router.get("/usage")
def usage(days: int = 30):
    return usage_service.summary(max(1, min(days, 365)))


@router.get("/backups")
def list_backups():
    return {"backups": backup_service.list_backups(), "folder": str(backup_service.backup_dir())}


@router.post("/backups")
def take_backup(admin: dict = Depends(current_admin)):
    try:
        made = backup_service.take()
    except backup_service.BackupError as exc:
        raise HTTPException(status_code=500, detail=f"Backup failed: {exc}") from exc
    _audit(admin, "backup.taken", made["name"])
    return made


@router.post("/backups/{name}/restore")
def restore_backup(name: str, admin: dict = Depends(current_admin)):
    try:
        result = backup_service.restore(name)
    except backup_service.BackupError as exc:
        raise HTTPException(status_code=400, detail=f"Not restored: {exc}") from exc
    # Written after the restore, so the restored log records it.
    _audit(admin, "backup.restored", name, f"previous state kept as {result['previous']}")
    return result


@router.get("/papers/pending")
def pending_papers():
    """Papers awaiting review, oldest first, with the full record payload."""
    out = []
    for s in AccountStore.instance().pending_submissions():
        person = notify_service.researcher(s["researcher_id"]) or {}
        out.append(
            {
                "id": s["id"],
                "kind": s["kind"],
                "researcher_id": s["researcher_id"],
                # A reviewer judges a paper by who sent it; a number says nothing.
                "researcher_name": person.get("full_name"),
                "title": s["title"],
                "submitted_at": s["submitted_at"],
                "record": json.loads(s["record_json"]),
            }
        )
    return out


@router.post("/papers/{sub_id}/approve")
def approve_paper(sub_id: int, admin: dict = Depends(current_admin)):
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
    if sub["kind"] == "library":
        from app.services import library_service

        library_service.approve_library(json.loads(sub["record_json"]), merged)
    if merged == 0 and sub["kind"] in ("publication", "upload"):
        log.warning(
            "Approval of submission %s (kind=%s) merged 0 staged chunks — "
            "it will not be searchable via the chatbot until re-indexed.",
            sub_id,
            sub["kind"],
        )
    store.set_submission_status(sub_id, "approved")
    _audit(admin, "paper.approved", f"submission {sub_id}", sub["title"])
    notify_service.paper_decided(sub, approved=True)
    alerts_service.run_in_background()  # someone may be waiting for this paper
    return {"status": "approved", "id": sub_id, "chunks_merged": merged}


@router.post("/papers/{sub_id}/reject")
def reject_paper(sub_id: int, body: RejectBody, admin: dict = Depends(current_admin)):
    """Reject a pending paper; its staged chunks are discarded. For a PDF
    upload, also deletes the uploaded file and its uploads-table row so a
    rejected paper can never be picked up by a full index rebuild."""
    store = AccountStore.instance()
    sub = store.get_submission(sub_id)
    if sub is None:
        raise HTTPException(status_code=404, detail="No such submission")
    staging.discard_staged(sub_id)
    if sub["kind"] == "library":
        from app.services import library_service

        library_service.discard_library(json.loads(sub["record_json"]))
    if sub["kind"] == "upload":
        from app.routers.papers import UPLOADS_DIR

        filename = json.loads(sub["record_json"]).get("filename")
        if filename:
            (UPLOADS_DIR / filename).unlink(missing_ok=True)
        store.delete_upload_for_submission(sub_id)
    store.set_submission_status(sub_id, "rejected", note=body.note)
    _audit(admin, "paper.rejected", f"submission {sub_id}", sub["title"])
    notify_service.paper_decided(sub, False, body.note)
    return {"status": "rejected", "id": sub_id}
