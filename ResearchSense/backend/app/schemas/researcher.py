"""Researcher (faculty profile) schemas."""

from __future__ import annotations

from pydantic import BaseModel, field_validator

from app.core.tenancy import institution_name
from app.schemas.publication import PublicationRef
from app.schemas.topic import TopicRef


class CollaborationSuggestion(BaseModel):
    """A recommended researcher to collaborate with."""

    researcher_id: int
    full_name: str
    designation: str
    department: str
    campus: str = ""
    similarity_score: float
    shared_topics: list[str] = []
    shared_count: int = 0
    copublications: int = 0
    past_coauthor: bool = False
    same_campus: bool = False
    relevance: float = 0.0
    international: bool = False


class Researcher(BaseModel):
    """Summary card for a faculty member (used in directory/list views)."""

    researcher_id: int
    full_name: str
    designation: str
    academic_rank: str = ""
    department: str
    campus: str = "Islamabad (E-8)"
    institution: str = ""
    email: str | None = None
    orcid_id: str | None = None
    photo_url: str | None = None
    expertise: str = ""  # real research areas text from the faculty page
    publication_count: int = 0
    citation_count: int = 0
    topics: list[TopicRef] = []
    research_areas: list[str] = []
    source: str = "scraped"

    @field_validator("institution", mode="before")
    @classmethod
    def _configured_institution(cls, _value: str) -> str:
        """Report the institution this workspace belongs to (empty for the
        neutral product-only look), never a name baked into the seed data — so
        the API stays institution-agnostic regardless of whose data populated
        it. The demo corpus uses RS_INSTITUTION_NAME; an institution that
        signed up is branded with the name it registered."""
        return institution_name()


class ResearcherDetail(Researcher):
    """Full profile including bio, publications and collaboration hints."""

    profile_bio: str = ""
    education: str = ""  # real degree, field and university from the faculty page
    google_scholar_id: str | None = None
    scopus_id: str | None = None
    publications: list[PublicationRef] = []
    collaborators: list[CollaborationSuggestion] = []
    international_collaborations: list[dict] = []
