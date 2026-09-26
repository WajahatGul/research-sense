"""Search-as-you-type suggestions."""

from __future__ import annotations

from fastapi import APIRouter, Query

from app.services.typeahead_service import Suggestion, suggest

router = APIRouter(prefix="/api/suggest", tags=["search"])


@router.get("", response_model=list[Suggestion])
def get_suggestions(
    q: str = "",
    scope: str | None = None,
    limit: int = Query(5, ge=1, le=10),
):
    return suggest(q, scope, limit)
