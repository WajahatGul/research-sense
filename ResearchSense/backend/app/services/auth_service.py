"""Business logic for profile claiming, login, and sessions."""
from __future__ import annotations

import os
import secrets

from fastapi import HTTPException

from app.core.security import create_token, hash_password, verify_password
from app.repositories.accounts import AccountStore
from app.repositories.base import ResearcherRepository
from app.schemas.auth import MeResponse, TokenResponse, UploadedPaper
from app.services.orcid_service import OrcidVerificationError, verify_claim


class AuthService:
    def __init__(self, researchers: ResearcherRepository):
        self._researchers = researchers
        self._store = AccountStore.instance()

    def claim(self, researcher_id: int, orcid_id: str, password: str) -> TokenResponse:
        researcher = self._researchers.get(researcher_id)
        if researcher is None:
            raise HTTPException(status_code=404, detail="Researcher not found")
        if self._store.account_for_researcher(researcher_id):
            raise HTTPException(
                status_code=409, detail="This profile is already claimed")
        if self._store.get_account(orcid_id):
            raise HTTPException(
                status_code=409, detail="This ORCID iD already has an account")
        # Identity check: the name on the public ORCID record must match the
        # profile being claimed, so nobody can claim someone else's profile.
        try:
            verify_claim(orcid_id, researcher.full_name)
        except OrcidVerificationError as exc:
            raise HTTPException(status_code=403, detail=str(exc))
        self._store.create_account(orcid_id, researcher_id, hash_password(password))
        return TokenResponse(
            token=create_token(orcid_id, "researcher"),
            role="researcher",
            researcher_id=researcher_id,
            full_name=researcher.full_name,
        )

    def login(self, orcid_id: str, password: str) -> TokenResponse:
        account = self._store.get_account(orcid_id)
        if (account is None or not account["active"]
                or not verify_password(password, account["password_hash"])):
            # One message for every failure mode: no account enumeration.
            raise HTTPException(status_code=401, detail="Invalid ORCID iD or password")
        researcher = self._researchers.get(account["researcher_id"])
        return TokenResponse(
            token=create_token(orcid_id, "researcher"),
            role="researcher",
            researcher_id=account["researcher_id"],
            full_name=researcher.full_name if researcher else None,
        )

    def admin_login(self, username: str, password: str) -> TokenResponse:
        expected_user = os.getenv("ADMIN_USERNAME", "admin")
        expected_pass = os.getenv("ADMIN_PASSWORD", "")
        if not expected_pass:
            raise HTTPException(
                status_code=503,
                detail="Admin login is not configured (set ADMIN_PASSWORD in .env)")
        if not (secrets.compare_digest(username, expected_user)
                and secrets.compare_digest(password, expected_pass)):
            raise HTTPException(status_code=401, detail="Invalid admin credentials")
        return TokenResponse(token=create_token(username, "admin"), role="admin")

    def me(self, token_payload: dict) -> MeResponse:
        if token_payload.get("role") == "admin":
            return MeResponse(role="admin")
        orcid_id = token_payload.get("sub", "")
        account = self._store.get_account(orcid_id)
        if account is None or not account["active"]:
            raise HTTPException(status_code=401, detail="Account not found or disabled")
        researcher = self._researchers.get(account["researcher_id"])
        uploads = [UploadedPaper(**u)
                   for u in self._store.uploads_for(account["researcher_id"])]
        return MeResponse(
            role="researcher",
            orcid_id=orcid_id,
            researcher_id=account["researcher_id"],
            full_name=researcher.full_name if researcher else None,
            uploads=uploads,
        )
