"""Schemas for institution workspaces and CV-assisted onboarding."""

from __future__ import annotations

import re
from typing import Annotated

from pydantic import BaseModel, BeforeValidator, Field
from pydantic_core import PydanticCustomError

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_EMAIL_HINT = "Enter a valid email address, e.g. name@university.edu."


def _clean_email(value: str) -> str:
    """Validate an email with a plain, human error.

    Pydantic's ``pattern=`` puts the raw regex in the response, which reached
    users as "String should match pattern ..." — the same leak the ORCID field
    already had to fix.
    """
    if not isinstance(value, str):
        raise PydanticCustomError("email", _EMAIL_HINT)
    v = value.strip().lower()
    if not _EMAIL_RE.match(v):
        raise PydanticCustomError("email", _EMAIL_HINT)
    return v


Email = Annotated[str, BeforeValidator(_clean_email)]


class WorkspaceSignup(BaseModel):
    """Create a workspace for an institution that is not in the demo corpus."""

    email: Email = Field(max_length=200)
    password: str = Field(min_length=8, max_length=128)
    institution_name: str = Field(min_length=2, max_length=200)
    full_name: str = Field(min_length=2, max_length=200)
    department: str = Field(default="", max_length=120)
    campus: str = Field(default="Main campus", max_length=120)
    orcid_id: str | None = None


class WorkspaceLogin(BaseModel):
    email: Email = Field(max_length=200)
    password: str


class WorkspaceSession(BaseModel):
    token: str
    role: str = "workspace"
    workspace_id: str
    institution_name: str
    full_name: str
    researcher_id: int


class CvText(BaseModel):
    text: str = Field(min_length=20, max_length=40000)


class CvPublication(BaseModel):
    title: str = Field(min_length=3, max_length=300)
    publication_year: int | None = None
    journal_name: str = ""
    doi: str | None = None


class CvDraft(BaseModel):
    """The editable review form: what was read from the CV, and what the
    researcher accepts. Never written until it comes back from the user."""

    full_name: str = ""
    designation: str = ""
    department: str = ""
    institution: str = ""
    education: str = ""
    profile_bio: str = ""
    research_areas: list[str] = []
    publications: list[CvPublication] = []


class CvApplyResult(BaseModel):
    publications_added: int
    research_areas: list[str]
    message: str


class WorkspaceDoi(BaseModel):
    doi: str = Field(min_length=6, max_length=300)
