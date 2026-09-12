"""Self-service onboarding for an institution that is not in the demo corpus.

Sign up, get an empty workspace branded with your institution, then fill it by
pasting a CV (reviewed and edited before anything is saved) or by DOI.
"""

from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException

from app.core.security import (
    create_token,
    current_user,
    hash_password,
    verify_password,
)
from app.repositories.workspaces import WorkspaceStore
from app.schemas.workspace import (
    CvApplyResult,
    CvDraft,
    CvText,
    WorkspaceDoi,
    WorkspaceLogin,
    WorkspaceSession,
    WorkspaceSignup,
)
from app.services import cv_service, workspace_service
from app.services.rag import workspace_index
from app.services.submission_service import SubmissionError, fetch_doi_metadata

router = APIRouter(prefix="/api/workspace", tags=["workspace"])


def _session(account: dict, institution_name: str) -> WorkspaceSession:
    return WorkspaceSession(
        token=create_token(
            account["email"], "workspace", workspace=account["workspace_id"]
        ),
        workspace_id=account["workspace_id"],
        institution_name=institution_name,
        full_name=account["full_name"],
        researcher_id=account["researcher_id"],
    )


def _account(user: dict = Depends(current_user)) -> dict:
    """The signed-in workspace account, or 403 for demo/ORCID sessions."""
    if user.get("role") != "workspace":
        raise HTTPException(
            status_code=403,
            detail="This action needs an institution workspace account.",
        )
    account = WorkspaceStore.instance().account_by_email(str(user.get("sub") or ""))
    if account is None:
        raise HTTPException(status_code=401, detail="Session expired or invalid")
    return account


@router.post("/signup", response_model=WorkspaceSession)
def signup(payload: WorkspaceSignup):
    store = WorkspaceStore.instance()
    if store.account_by_email(payload.email):
        raise HTTPException(
            status_code=409, detail="An account already exists for this email."
        )
    account = store.create(
        email=payload.email,
        password_hash=hash_password(payload.password),
        institution_name=payload.institution_name.strip(),
        full_name=payload.full_name.strip(),
        department=payload.department.strip(),
        campus=payload.campus.strip() or "Main campus",
        orcid_id=payload.orcid_id,
    )
    return _session(account, account["institution_name"])


@router.post("/login", response_model=WorkspaceSession)
def login(payload: WorkspaceLogin):
    store = WorkspaceStore.instance()
    account = store.account_by_email(payload.email)
    if account is None or not verify_password(
        payload.password, account["password_hash"]
    ):
        # One message for every failure mode: no account enumeration.
        raise HTTPException(status_code=401, detail="Invalid email or password")
    workspace = store.workspace(account["workspace_id"]) or {}
    return _session(account, workspace.get("institution_name", ""))


@router.get("/me", response_model=WorkspaceSession)
def me(account: dict = Depends(_account)):
    workspace = WorkspaceStore.instance().workspace(account["workspace_id"]) or {}
    return _session(account, workspace.get("institution_name", ""))


@router.post("/cv/parse", response_model=CvDraft)
def parse_cv(payload: CvText, account: dict = Depends(_account)):
    """Read a CV into a draft. Nothing is saved — the client shows this in an
    editable form and posts it back to /cv/apply once the user accepts it."""
    return CvDraft(**cv_service.parse_cv(payload.text))


@router.post("/cv/apply", response_model=CvApplyResult)
def apply_cv(
    payload: CvDraft,
    background: BackgroundTasks,
    account: dict = Depends(_account),
):
    """Write the reviewed profile and publications into the workspace."""
    workspace = account["workspace_id"]
    researcher_id = account["researcher_id"]
    try:
        result = workspace_service.apply_profile(
            workspace, researcher_id, payload.model_dump()
        )
        added = workspace_service.add_publications(
            workspace,
            researcher_id,
            [p.model_dump() for p in payload.publications],
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    # Re-index in the background so the assistant can answer about this profile
    # and these papers; the response does not wait for the embedding model.
    background.add_task(workspace_index.rebuild_quietly, workspace)

    return CvApplyResult(
        publications_added=added,
        research_areas=result["research_areas"],
        message=(
            f"Saved your profile and added {added} publication(s). "
            "Your portal now reflects your own data."
        ),
    )


@router.post("/publications/doi", response_model=CvApplyResult)
def add_by_doi(
    payload: WorkspaceDoi,
    background: BackgroundTasks,
    account: dict = Depends(_account),
):
    """Add one verified paper to the workspace by its DOI."""
    try:
        meta = fetch_doi_metadata(payload.doi)
    except SubmissionError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    added = workspace_service.add_publications(
        account["workspace_id"],
        account["researcher_id"],
        [
            {
                "title": meta.get("title", ""),
                "publication_year": meta.get("publication_year"),
                "journal_name": meta.get("journal_name", ""),
                "doi": meta.get("doi"),
                "citation_count": meta.get("citation_count", 0),
                "publication_type": meta.get("publication_type", "journal"),
                "source": "doi",
            }
        ],
    )
    if added:
        background.add_task(workspace_index.rebuild_quietly, account["workspace_id"])
    return CvApplyResult(
        publications_added=added,
        research_areas=[],
        message=(
            "Paper added to your workspace."
            if added
            else "That paper is already in your workspace."
        ),
    )
