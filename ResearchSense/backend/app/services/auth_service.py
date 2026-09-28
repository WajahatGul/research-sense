"""Business logic for profile claiming, login, and sessions."""

from __future__ import annotations

import json

from fastapi import HTTPException

from app.core import throttle
from app.core.security import create_token, hash_password, verify_password
from app.repositories.accounts import AccountStore
from app.repositories.base import ResearcherRepository
from app.schemas.auth import ClaimResult, MeResponse, TokenResponse, UploadedPaper
from app.services.orcid_service import (
    OrcidVerificationError,
    fetch_record_employers,
    verify_claim,
)

PENDING_MESSAGE = (
    "Your claim is waiting for an administrator to confirm it is you. "
    "You can sign in with this ORCID iD and password once it is approved."
)


class AuthService:
    def __init__(self, researchers: ResearcherRepository):
        self._researchers = researchers
        self._store = AccountStore.instance()

    def claim(self, researcher_id: int, orcid_id: str, password: str) -> ClaimResult:
        """A claim made by typing an ORCID iD waits for an administrator.

        ORCID iDs are public (orcid.org, OpenAlex), so typing one proves
        nothing: anyone could enter the real researcher's iD and a password
        of their own. The registry name check only filters out mistakes; the
        claim then waits, with the ORCID record's names and employers stored
        for the admin to judge. Signing in at orcid.org (claim_verified) is
        proof, and goes live at once.
        """
        # Throttled as well as login: every attempt calls the public ORCID
        # registry, so repeated guessing is abuse of someone else's service.
        throttle.check(f"claim:{orcid_id}")
        researcher = self._researchers.get(researcher_id)
        if researcher is None:
            raise HTTPException(status_code=404, detail="Researcher not found")
        if self._store.account_for_researcher(researcher_id):
            raise HTTPException(
                status_code=409, detail="This profile is already claimed"
            )
        if self._store.get_account(orcid_id):
            raise HTTPException(
                status_code=409, detail="This ORCID iD already has an account"
            )
        waiting = self._store.latest_claim_for_orcid(orcid_id)
        if waiting and waiting["status"] == "pending":
            raise HTTPException(
                status_code=409,
                detail="A claim with this ORCID iD is already waiting for approval.",
            )
        from app.core.config import settings

        # The DEV_ORCID iD from .env skips the checks for local testing.
        if settings.dev_orcid and orcid_id == settings.dev_orcid:
            return self._open_account(
                orcid_id, researcher_id, hash_password(password), researcher.full_name
            )
        try:
            names = verify_claim(orcid_id, researcher.full_name)
        except OrcidVerificationError as exc:
            throttle.record_failure(f"claim:{orcid_id}")
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        throttle.record_success(f"claim:{orcid_id}")
        evidence = {
            "orcid_names": names,
            "orcid_employers": fetch_record_employers(orcid_id),
        }
        self._store.create_claim(
            orcid_id, researcher_id, hash_password(password), json.dumps(evidence)
        )
        return ClaimResult(
            status="pending",
            message=PENDING_MESSAGE,
            researcher_id=researcher_id,
            full_name=researcher.full_name,
        )

    def _open_account(
        self, orcid_id: str, researcher_id: int, password_hash: str, full_name: str
    ) -> ClaimResult:
        self._store.create_account(orcid_id, researcher_id, password_hash)
        # Whoever else was waiting on this profile is not its owner.
        self._store.reject_pending_claims_for(
            researcher_id, "The profile's owner verified their identity."
        )
        return ClaimResult(
            status="approved",
            message="Your profile is yours. You are signed in.",
            token=create_token(orcid_id, "researcher"),
            role="researcher",
            researcher_id=researcher_id,
            full_name=full_name,
        )

    def approve_claim(self, claim_id: int) -> ClaimResult:
        claim = self._store.get_claim(claim_id)
        if claim is None or claim["status"] != "pending":
            raise HTTPException(status_code=404, detail="No such pending claim")
        if self._store.account_for_researcher(claim["researcher_id"]):
            raise HTTPException(status_code=409, detail="This profile is already claimed")
        if self._store.get_account(claim["orcid_id"]):
            raise HTTPException(
                status_code=409, detail="This ORCID iD already has an account"
            )
        researcher = self._researchers.get(claim["researcher_id"])
        self._store.set_claim_status(claim_id, "approved")
        result = self._open_account(
            claim["orcid_id"],
            claim["researcher_id"],
            claim["password_hash"],
            researcher.full_name if researcher else "",
        )
        # The admin approves on the claimant's behalf: no session for the admin.
        return result.model_copy(update={"token": None, "message": "Claim approved."})

    def reject_claim(self, claim_id: int, note: str | None) -> None:
        claim = self._store.get_claim(claim_id)
        if claim is None or claim["status"] != "pending":
            raise HTTPException(status_code=404, detail="No such pending claim")
        self._store.set_claim_status(claim_id, "rejected", note)

    def claim_verified(
        self, researcher_id: int, orcid_id: str, password: str
    ) -> ClaimResult:
        """Complete a claim where ORCID itself authenticated the person.

        The registry name check is deliberately skipped: signing in at
        orcid.org is stronger evidence than a name match, and a researcher
        whose ORCID record spells their name differently should not be blocked
        by the weaker test after passing the stronger one.
        """
        researcher = self._researchers.get(researcher_id)
        if researcher is None:
            raise HTTPException(status_code=404, detail="Researcher not found")
        if self._store.account_for_researcher(researcher_id):
            raise HTTPException(
                status_code=409, detail="This profile is already claimed"
            )
        if self._store.get_account(orcid_id):
            raise HTTPException(
                status_code=409, detail="This ORCID iD already has an account"
            )
        return self._open_account(
            orcid_id, researcher_id, hash_password(password), researcher.full_name
        )

    def login(self, orcid_id: str, password: str) -> TokenResponse:
        throttle.check(orcid_id)
        account = self._store.get_account(orcid_id)
        if account is None:
            # Say where a claim stands, but only to someone who knows its
            # password: otherwise it would reveal who has claimed what.
            claim = self._store.latest_claim_for_orcid(orcid_id)
            if claim and verify_password(password, claim["password_hash"]):
                throttle.record_success(orcid_id)
                if claim["status"] == "pending":
                    raise HTTPException(status_code=403, detail=PENDING_MESSAGE)
                if claim["status"] == "rejected":
                    reason = f" Reason: {claim['note']}" if claim.get("note") else ""
                    raise HTTPException(
                        status_code=403, detail="Your claim was not approved." + reason
                    )
        if (
            account is None
            or not account["active"]
            or not verify_password(password, account["password_hash"])
        ):
            throttle.record_failure(orcid_id)
            # One message for every failure mode: no account enumeration.
            raise HTTPException(status_code=401, detail="Invalid ORCID iD or password")
        throttle.record_success(orcid_id)
        researcher = self._researchers.get(account["researcher_id"])
        return TokenResponse(
            token=create_token(orcid_id, "researcher"),
            role="researcher",
            researcher_id=account["researcher_id"],
            full_name=researcher.full_name if researcher else None,
        )

    def admin_login(self, username: str, password: str) -> TokenResponse:
        from app.services import admin_accounts

        admin_accounts.ensure_first_admin()
        if not self._store.count_admins():
            raise HTTPException(
                status_code=503,
                detail="No administrator exists yet (set ADMIN_PASSWORD in .env "
                       "to create the first one)",
            )
        throttle.check(f"admin:{username}")
        admin = admin_accounts.authenticate(username, password)
        if admin is None:
            throttle.record_failure(f"admin:{username}")
            # Failed sign-ins are recorded too: repeated ones are the signal
            # that someone is guessing.
            self._store.record(username.strip().lower()[:40] or "?", "admin.login_failed")
            raise HTTPException(status_code=401, detail="Invalid admin credentials")
        throttle.record_success(f"admin:{username}")
        self._store.record(admin["username"], "admin.login")
        return TokenResponse(token=create_token(admin["username"], "admin"), role="admin")

    def me(self, token_payload: dict) -> MeResponse:
        if token_payload.get("role") == "admin":
            admin = self._store.get_admin(token_payload.get("sub", "")) or {}
            return MeResponse(role="admin", full_name=admin.get("username"),
                              password_weak=bool(admin.get("weak_password")))
        orcid_id = token_payload.get("sub", "")
        account = self._store.get_account(orcid_id)
        if account is None or not account["active"]:
            raise HTTPException(status_code=401, detail="Account not found or disabled")
        researcher = self._researchers.get(account["researcher_id"])
        uploads = [
            UploadedPaper(**u)
            for u in self._store.uploads_for(account["researcher_id"])
        ]
        return MeResponse(
            role="researcher",
            orcid_id=orcid_id,
            researcher_id=account["researcher_id"],
            full_name=researcher.full_name if researcher else None,
            uploads=uploads,
        )
