"""Anonymous usage events from the browser (see usage_service)."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel, Field

from app.services import usage_service

router = APIRouter(prefix="/api/events", tags=["usage"])


class Event(BaseModel):
    kind: str
    visitor: str = Field(max_length=64)
    detail: str = Field("", max_length=120)


@router.post("", status_code=204, response_class=Response)
def record_event(event: Event) -> Response:
    if event.kind not in usage_service.CLIENT_KINDS or not usage_service.VISITOR.match(
        event.visitor
    ):
        raise HTTPException(status_code=422, detail="Unknown event")
    usage_service.record(event.kind, event.visitor, event.detail)
    return Response(status_code=204)
