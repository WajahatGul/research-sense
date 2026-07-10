"""Admin endpoints: claimed accounts, activation, and data refresh."""
from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends

from app.core.deps import get_researcher_service
from app.core.security import current_admin
from app.repositories.accounts import AccountStore
from app.schemas.auth import ClaimedAccount
from app.services import refresh_service

router = APIRouter(prefix="/api/admin", tags=["admin"],
                   dependencies=[Depends(current_admin)])


@router.get("/accounts", response_model=list[ClaimedAccount])
def list_accounts():
    service = get_researcher_service()
    out = []
    for account in AccountStore.instance().list_accounts():
        researcher = service.get(account["researcher_id"])
        out.append(ClaimedAccount(
            orcid_id=account["orcid_id"],
            researcher_id=account["researcher_id"],
            full_name=researcher.full_name if researcher else "(unknown)",
            active=bool(account["active"]),
            created_at=account["created_at"],
        ))
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
