"""Authentication endpoints: claim, login, admin login, session info."""

from __future__ import annotations

from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse

from app.core.config import settings
from app.core.deps import get_auth_service
from app.core.security import current_user
from app.schemas.auth import (
    AdminLoginRequest,
    ClaimRequest,
    ClaimStart,
    LoginRequest,
    MeResponse,
    OrcidStart,
    TokenResponse,
)
from app.services import orcid_oauth
from app.services.auth_service import AuthService

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/claim", response_model=TokenResponse)
def claim_profile(
    payload: ClaimRequest,
    service: AuthService = Depends(get_auth_service),
):
    return service.claim(payload.researcher_id, payload.orcid_id, payload.password)


@router.get("/orcid/available", response_model=bool)
def orcid_sign_in_available() -> bool:
    """Whether the portal can offer "Verify with ORCID" (client configured)."""
    return orcid_oauth.available()


@router.post("/orcid/begin", response_model=OrcidStart)
def orcid_begin(payload: ClaimStart):
    """Hold the claim and hand back the ORCID URL to send the browser to."""
    if not orcid_oauth.available():
        raise HTTPException(
            status_code=503,
            detail="ORCID sign-in is not configured on this deployment.",
        )
    url = orcid_oauth.begin(payload.researcher_id, payload.password)
    return OrcidStart(authorize_url=url)


@router.get("/orcid/callback", include_in_schema=False)
def orcid_callback(
    state: str = "",
    code: str = "",
    error: str = "",
    service: AuthService = Depends(get_auth_service),
):
    """Where ORCID returns the browser. Always redirects to the portal.

    The outcome travels as a query parameter the portal consumes and clears,
    because this endpoint is reached by a full page load, not by fetch().
    """
    origin = settings.frontend_origin.rstrip("/")

    def back(params: str) -> RedirectResponse:
        return RedirectResponse(f"{origin}/portal?{params}", status_code=303)

    if error or not code or not state:
        return back("orcid_error=" + quote("ORCID sign-in was cancelled."))

    pending = orcid_oauth.take_pending(state)
    if pending is None:
        return back("orcid_error=" + quote("That sign-in expired. Please start again."))
    try:
        orcid_id = orcid_oauth.exchange(code)
        session = service.claim_verified(
            pending.researcher_id, orcid_id, pending.password
        )
    except ValueError as exc:
        return back("orcid_error=" + quote(str(exc)))
    except HTTPException as exc:
        return back("orcid_error=" + quote(str(exc.detail)))
    return back("orcid_token=" + quote(session.token))


@router.post("/login", response_model=TokenResponse)
def login(
    payload: LoginRequest,
    service: AuthService = Depends(get_auth_service),
):
    return service.login(payload.orcid_id, payload.password)


@router.post("/admin-login", response_model=TokenResponse)
def admin_login(
    payload: AdminLoginRequest,
    service: AuthService = Depends(get_auth_service),
):
    return service.admin_login(payload.username, payload.password)


@router.get("/me", response_model=MeResponse)
def me(
    token_payload: dict = Depends(current_user),
    service: AuthService = Depends(get_auth_service),
):
    return service.me(token_payload)


@router.get("/claimed", response_model=list[int])
def claimed_researcher_ids():
    """Public list of researcher ids with a claimed profile (for badges)."""
    from app.repositories.accounts import AccountStore

    return sorted(AccountStore.instance().claimed_researcher_ids())
