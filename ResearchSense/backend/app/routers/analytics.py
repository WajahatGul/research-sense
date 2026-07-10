"""Analytics endpoint."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from app.core.deps import get_analytics_service
from app.services.analytics_service import AnalyticsService

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


@router.get("")
def analytics_overview(
    service: AnalyticsService = Depends(get_analytics_service),
):
    return service.overview()
