"""Library endpoints: browse the studied papers, remove your own.

The list is public — the assistant already answers from these papers for
everyone, so hiding the catalogue would only confuse. Removal is restricted
to the researcher who added the paper, or an admin.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.core.security import current_user
from app.repositories.accounts import AccountStore
from app.services import library_service
from app.services.library_service import LibraryError

router = APIRouter(prefix="/api/library", tags=["library"])


class LibraryEntry(BaseModel):
    doi: str | None
    title: str
    year: int | str | None
    filename: str
    chunks: int
    added_at: str | None = None


class RemoveResult(BaseModel):
    title: str
    chunks_removed: int
    message: str


@router.get("", response_model=list[LibraryEntry])
def list_library():
    return library_service.list_library()


@router.delete("/{filename}", response_model=RemoveResult)
def remove_paper(
    filename: str,
    token_payload: dict = Depends(current_user),
):
    is_admin = token_payload.get("role") == "admin"
    requester_id = None
    if not is_admin:
        account = AccountStore.instance().get_account(token_payload.get("sub", ""))
        if account is None or not account["active"]:
            raise HTTPException(status_code=401,
                                detail="Account not found or disabled")
        requester_id = account["researcher_id"]
    try:
        result = library_service.remove_paper(filename, requester_id, is_admin)
    except LibraryError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    return RemoveResult(**result,
                        message="Removed from the library and the assistant.")
