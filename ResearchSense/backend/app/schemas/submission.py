"""Publication submission (DOI-based and manual) schemas."""
from __future__ import annotations

from pydantic import BaseModel, Field


class DoiRequest(BaseModel):
    """A DOI to preview or submit, e.g. '10.1145/3576915' or a doi.org URL."""

    doi: str = Field(min_length=6, max_length=300)


class DoiPreview(BaseModel):
    """Normalized registry metadata (Crossref, DataCite fallback) shown at
    the verify step, with the OpenAlex concept fingerprint."""

    doi: str
    title: str
    authors: list[str]
    publication_year: int
    journal_name: str
    publication_type: str
    citation_count: int
    abstract: str
    concepts: list[str] = []
    topics: list[str] = []
    duplicate: bool
    duplicate_of: str | None = None
    # False when the submitting researcher is not in the paper's author list.
    authorship_ok: bool = True
    authorship_message: str | None = None


class ManualSubmission(BaseModel):
    """Manually entered publication details (used when no DOI exists)."""

    title: str = Field(min_length=5, max_length=300)
    journal_name: str = Field(default="", max_length=300)
    publication_year: int = Field(ge=1950, le=2100)
    publication_type: str = Field(default="journal", pattern="^(journal|conference)$")


class SubmissionResult(BaseModel):
    """The stored publication, echoed back after a successful submission."""

    publication_id: int
    title: str
    publication_year: int
    journal_name: str
    message: str
