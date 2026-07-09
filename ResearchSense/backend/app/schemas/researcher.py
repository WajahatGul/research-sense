"""Researcher (faculty profile) schemas."""
from __future__ import annotations

from pydantic import BaseModel

from app.schemas.publication import PublicationRef
from app.schemas.topic import TopicRef


class CollaborationSuggestion(BaseModel):
    """A recommended researcher to collaborate with."""

    researcher_id: int
    full_name: str
    designation: str
    department: str
    similarity_score: float
    basis: str = "shared topics"


class Researcher(BaseModel):
    """Summary card for a faculty member (used in directory/list views)."""

    researcher_id: int
    full_name: str
    designation: str
    department: str
    institution: str = "Bahria University, Islamabad (E-8)"
    email: str | None = None
    orcid_id: str | None = None
    photo_url: str | None = None
    publication_count: int = 0
    citation_count: int = 0
    topics: list[TopicRef] = []
    source: str = "scraped"


class ResearcherDetail(Researcher):
    """Full profile including bio, publications and collaboration hints."""

    profile_bio: str = ""
    google_scholar_id: str | None = None
    scopus_id: str | None = None
    publications: list[PublicationRef] = []
    collaborators: list[CollaborationSuggestion] = []
