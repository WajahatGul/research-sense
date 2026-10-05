"""Saved searches with email alerts (see alerts_service)."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services import alerts_service

router = APIRouter(prefix="/api/alerts", tags=["alerts"])


class NewAlert(BaseModel):
    email: str = Field(max_length=200)
    kind: str
    filters: dict[str, str | int | None]


class TokenBody(BaseModel):
    token: str = Field(max_length=100)


@router.post("")
def create_alert(body: NewAlert):
    try:
        return alerts_service.create(body.email, body.kind, body.filters)
    except alerts_service.AlertError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/confirm")
def confirm_alert(body: TokenBody):
    try:
        return alerts_service.confirm(body.token)
    except alerts_service.AlertError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/stop")
def stop_alert(body: TokenBody):
    try:
        return alerts_service.stop(body.token)
    except alerts_service.AlertError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
