"""Faculty paper endpoints: PDF upload (RAG index) and publication submission
(DOI-based via Crossref, or manual entry) per the proposal's ingestion pipeline."""
from __future__ import annotations

import re
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from app.core.security import current_user
from app.repositories import loader
from app.repositories.accounts import AccountStore
from app.schemas.submission import (DoiPreview, DoiRequest, ManualSubmission,
                                    SubmissionResult)
from app.services import submission_service
from app.services.rag import indexer
from app.services.submission_service import SubmissionError

router = APIRouter(prefix="/api/papers", tags=["papers"])

UPLOADS_DIR = Path(__file__).resolve().parents[2] / "papers" / "uploads"
MAX_BYTES = 15 * 1024 * 1024  # 15 MB


def _safe_filename(title: str, researcher_id: int) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:60]
    return f"upload-{researcher_id}-{slug}.pdf"


def _submitting_researcher(token_payload: dict) -> dict:
    """Resolve the authenticated faculty account to its researcher record."""
    if token_payload.get("role") != "researcher":
        raise HTTPException(status_code=403, detail="Faculty account required")
    account = AccountStore.instance().get_account(token_payload["sub"])
    if account is None or not account["active"]:
        raise HTTPException(status_code=401,
                            detail="Account not found or disabled")
    researcher = next(
        (r for r in loader.load("researchers")
         if r["researcher_id"] == account["researcher_id"]), None)
    if researcher is None:
        raise HTTPException(status_code=404, detail="Researcher not found")
    return researcher


@router.post("/upload")
async def upload_paper(
    title: str = Form(min_length=5, max_length=300),
    file: UploadFile = File(...),
    token_payload: dict = Depends(current_user),
):
    if token_payload.get("role") != "researcher":
        raise HTTPException(status_code=403, detail="Faculty account required")

    store = AccountStore.instance()
    account = store.get_account(token_payload["sub"])
    if account is None or not account["active"]:
        raise HTTPException(status_code=401, detail="Account not found or disabled")
    researcher_id = account["researcher_id"]

    data = await file.read()
    if len(data) > MAX_BYTES:
        raise HTTPException(status_code=413, detail="PDF larger than 15 MB")
    if data[:5] != b"%PDF-":
        raise HTTPException(status_code=400, detail="The file is not a PDF")

    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    filename = _safe_filename(title, researcher_id)
    path = UPLOADS_DIR / filename
    path.write_bytes(data)

    from app.core.deps import get_researcher_service

    researcher = get_researcher_service().get(researcher_id)
    author = researcher.full_name if researcher else "a Bahria researcher"
    try:
        added = indexer.add_paper(path, title.strip(), author, researcher_id)
    except ValueError as exc:
        path.unlink(missing_ok=True)  # reject unindexable files loudly
        raise HTTPException(status_code=400, detail=str(exc))

    store.record_upload(researcher_id, title.strip(), filename)
    return {"status": "indexed", "chunks_added": added,
            "message": "Your paper is now part of the assistant's knowledge."}


@router.post("/doi/preview", response_model=DoiPreview)
def doi_preview(
    payload: DoiRequest,
    token_payload: dict = Depends(current_user),
):
    """Step 1 of DOI submission: registry metadata + authorship verdict."""
    researcher = _submitting_researcher(token_payload)
    try:
        return submission_service.preview_doi(
            payload.doi, researcher, token_payload.get("sub"))
    except SubmissionError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.post("/doi/submit", response_model=SubmissionResult)
def doi_submit(
    payload: DoiRequest,
    token_payload: dict = Depends(current_user),
):
    """Step 2 of DOI submission: verified by the user — store the record.
    Authorship is re-verified server-side; the preview verdict is advisory."""
    researcher = _submitting_researcher(token_payload)
    try:
        record = submission_service.submit_doi(
            payload.doi, researcher, token_payload.get("sub"))
    except SubmissionError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return SubmissionResult(
        publication_id=record["publication_id"],
        title=record["title"],
        publication_year=record["publication_year"],
        journal_name=record["journal_name"],
        message=("Publication added. It now appears on your profile, in "
                 "Publications, in Analytics, and the assistant can answer "
                 "questions about it."),
    )


@router.post("/manual", response_model=SubmissionResult)
def manual_submit(
    payload: ManualSubmission,
    token_payload: dict = Depends(current_user),
):
    """Manual publication entry, used when the work has no DOI."""
    researcher = _submitting_researcher(token_payload)
    try:
        record = submission_service.submit_manual(
            title=payload.title,
            journal_name=payload.journal_name,
            publication_year=payload.publication_year,
            publication_type=payload.publication_type,
            submitter=researcher,
        )
    except SubmissionError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return SubmissionResult(
        publication_id=record["publication_id"],
        title=record["title"],
        publication_year=record["publication_year"],
        journal_name=record["journal_name"],
        message="Publication added to your profile and the database.",
    )
