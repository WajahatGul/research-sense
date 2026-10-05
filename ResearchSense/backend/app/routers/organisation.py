"""Who this deployment serves and the vocabulary it uses."""

from __future__ import annotations

from fastapi import APIRouter

from app.core.organisation import Organisation, organisation

router = APIRouter(prefix="/api/organisation", tags=["organisation"])


@router.get("", response_model=Organisation)
def get_organisation():
    return organisation()
