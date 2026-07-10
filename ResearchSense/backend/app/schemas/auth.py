"""Schemas for faculty accounts and sessions."""
from __future__ import annotations

from pydantic import BaseModel, Field

ORCID_PATTERN = r"^\d{4}-\d{4}-\d{4}-\d{3}[\dX]$"


class ClaimRequest(BaseModel):
    """A researcher claims their profile with their ORCID iD and a password."""

    researcher_id: int
    orcid_id: str = Field(pattern=ORCID_PATTERN,
                          description="Format: 0000-0000-0000-0000")
    password: str = Field(min_length=8, max_length=128)


class LoginRequest(BaseModel):
    orcid_id: str = Field(pattern=ORCID_PATTERN)
    password: str


class AdminLoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    token: str
    role: str  # "researcher" | "admin"
    researcher_id: int | None = None
    full_name: str | None = None


class UploadedPaper(BaseModel):
    title: str
    filename: str
    uploaded_at: str


class MeResponse(BaseModel):
    role: str
    orcid_id: str | None = None
    researcher_id: int | None = None
    full_name: str | None = None
    uploads: list[UploadedPaper] = []


class ClaimedAccount(BaseModel):
    orcid_id: str
    researcher_id: int
    full_name: str
    active: bool
    created_at: str
