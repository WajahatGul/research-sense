"""Stats endpoint."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from app.core.deps import get_stats_service
from app.schemas.common import Stats
from app.services.stats_service import StatsService

router = APIRouter(prefix="/api/stats", tags=["stats"])


@router.get("", response_model=Stats)
def get_stats(service: StatsService = Depends(get_stats_service)):
    return service.get()
