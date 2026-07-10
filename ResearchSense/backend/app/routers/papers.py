"""Faculty paper upload: store the PDF and add it to the live RAG index."""
from __future__ import annotations

import re
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from app.core.security import current_user
from app.repositories.accounts import AccountStore
from app.services.rag import indexer

router = APIRouter(prefix="/api/papers", tags=["papers"])

UPLOADS_DIR = Path(__file__).resolve().parents[2] / "papers" / "uploads"
MAX_BYTES = 15 * 1024 * 1024  # 15 MB


def _safe_filename(title: str, researcher_id: int) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:60]
    return f"upload-{researcher_id}-{slug}.pdf"


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
