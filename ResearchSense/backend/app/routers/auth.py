"""Authentication endpoints: claim, login, admin login, session info."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from app.core.deps import get_auth_service
from app.core.security import current_user
from app.schemas.auth import (
    AdminLoginRequest,
    ClaimRequest,
    LoginRequest,
    MeResponse,
    TokenResponse,
)
from app.services.auth_service import AuthService

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/claim", response_model=TokenResponse)
def claim_profile(
    payload: ClaimRequest,
    service: AuthService = Depends(get_auth_service),
):
    return service.claim(payload.researcher_id, payload.orcid_id, payload.password)


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
