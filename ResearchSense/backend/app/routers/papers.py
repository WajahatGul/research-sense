"""Faculty paper endpoints: PDF upload (RAG index) and publication submission
(DOI-based via Crossref, or manual entry) per the proposal's ingestion pipeline."""

from __future__ import annotations

import re
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from app.core.security import current_user
from app.repositories import loader
from app.repositories.accounts import AccountStore
from app.schemas.submission import (
    DoiPreview,
    DoiRequest,
    ManualSubmission,
    StudyResult,
    SubmissionResult,
    SubmissionStatus,
)
from app.services import library_service, submission_service
from app.services.library_service import LibraryError
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
        raise HTTPException(status_code=401, detail="Account not found or disabled")
    researcher = next(
        (
            r
            for r in loader.load("researchers")
            if r["researcher_id"] == account["researcher_id"]
        ),
        None,
    )
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
    from app.repositories.accounts import AccountStore as _Store
    from app.services import staging

    researcher = get_researcher_service().get(researcher_id)
    author = researcher.full_name if researcher else "a university researcher"
    try:
        text = indexer.extract_pdf_text(path)
    except ValueError as exc:
        path.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    header = f'From the paper "{title.strip()}" by {author}: '
    chunks = [
        {
            "text": header + piece,
            "kind": "paper",
            "ref_id": researcher_id,
            "label": f"Paper: {title.strip()[:70]} (uploaded)",
        }
        for piece in indexer._split(text)
    ]
    if not chunks:
        path.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail="The PDF is too short to index")
    import json as _json

    sub_id = _Store.instance().create_submission(
        "upload",
        researcher_id,
        title.strip(),
        _json.dumps({"filename": filename, "title": title.strip()}),
    )
    staging.stage_chunks(sub_id, chunks)
    store.record_upload(researcher_id, title.strip(), filename)
    return {
        "status": "pending",
        "submission_id": sub_id,
        "message": "Your paper is awaiting admin approval. It will be "
        "searchable the moment it is approved.",
    }


@router.get("/mine", response_model=list[SubmissionStatus])
def my_submissions(token_payload: dict = Depends(current_user)):
    """The signed-in researcher's paper submissions with approval status."""
    researcher = _submitting_researcher(token_payload)
    return AccountStore.instance().submissions_for(researcher["researcher_id"])


@router.post("/doi/preview", response_model=DoiPreview)
def doi_preview(
    payload: DoiRequest,
    token_payload: dict = Depends(current_user),
):
    """Step 1 of DOI submission: registry metadata + authorship verdict."""
    researcher = _submitting_researcher(token_payload)
    try:
        return submission_service.preview_doi(
            payload.doi, researcher, token_payload.get("sub")
        )
    except SubmissionError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


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
            payload.doi, researcher, token_payload.get("sub")
        )
    except SubmissionError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return SubmissionResult(
        publication_id=None,
        title=record["title"],
        publication_year=record["publication_year"],
        journal_name=record["journal_name"],
        message=(
            "Submitted for admin approval. It will appear on your "
            "profile and in Publications once approved."
        ),
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
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return SubmissionResult(
        publication_id=None,
        title=record["title"],
        publication_year=record["publication_year"],
        journal_name=record["journal_name"],
        message=(
            "Submitted for admin approval. It will appear on your "
            "profile and in Publications once approved."
        ),
    )


@router.post("/study/doi", response_model=StudyResult)
def study_doi(
    payload: DoiRequest,
    token_payload: dict = Depends(current_user),
):
    """Add ANY paper to the assistant's library by DOI — fetches the
    open-access PDF and indexes its full text. No authorship required and no
    profile attribution: this is for studying papers, not claiming them."""
    researcher = _submitting_researcher(token_payload)
    try:
        result = library_service.study_doi(
            payload.doi, added_by=researcher["researcher_id"]
        )
    except LibraryError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return StudyResult(
        **result,
        message=(
            "Added to the library. Ask the assistant anything about "
            "this paper — it has read the full text."
        ),
    )


@router.post("/study/upload", response_model=StudyResult)
async def study_upload(
    title: str = Form(min_length=5, max_length=300),
    file: UploadFile = File(...),
    token_payload: dict = Depends(current_user),
):
    """Library fallback for papers without an open-access PDF: upload it."""
    researcher = _submitting_researcher(token_payload)
    data = await file.read()
    try:
        result = library_service.study_upload(
            data, title, added_by=researcher["researcher_id"]
        )
    except LibraryError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return StudyResult(
        **result,
        message=(
            "Added to the library. Ask the assistant anything about "
            "this paper — it has read the full text."
        ),
    )
