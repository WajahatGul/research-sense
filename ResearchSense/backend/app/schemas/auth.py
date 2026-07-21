"""Schemas for faculty accounts and sessions."""
from __future__ import annotations

import re
from typing import Annotated

from pydantic import BaseModel, BeforeValidator, Field
from pydantic_core import PydanticCustomError

ORCID_PATTERN = r"^\d{4}-\d{4}-\d{4}-\d{3}[\dX]$"
_ORCID_RE = re.compile(ORCID_PATTERN)
_ORCID_HINT = "Enter a valid 16-digit ORCID iD, e.g. 0000-0002-1825-0097."


def _normalize_orcid(value: str) -> str:
    """Accept an ORCID with or without dashes and validate it with a plain,
    human error — never the raw regex pattern. 16 bare digits/X are dashed
    automatically (0000000218250097 -> 0000-0000-1825-0097)."""
    if not isinstance(value, str):
        raise PydanticCustomError("orcid", _ORCID_HINT)
    v = value.strip().upper()
    bare = v.replace("-", "").replace(" ", "")
    if re.fullmatch(r"\d{15}[\dX]", bare):
        v = f"{bare[0:4]}-{bare[4:8]}-{bare[8:12]}-{bare[12:16]}"
    if not _ORCID_RE.match(v):
        raise PydanticCustomError("orcid", _ORCID_HINT)
    return v


OrcidId = Annotated[str, BeforeValidator(_normalize_orcid)]


class ClaimRequest(BaseModel):
    """A researcher claims their profile with their ORCID iD and a password."""

    researcher_id: int
    orcid_id: OrcidId = Field(description="Format: 0000-0000-0000-0000")
    password: str = Field(min_length=8, max_length=128)


class LoginRequest(BaseModel):
    orcid_id: OrcidId
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
