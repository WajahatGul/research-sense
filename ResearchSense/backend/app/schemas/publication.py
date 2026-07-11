"""Publication schemas."""
from __future__ import annotations

from pydantic import BaseModel

from app.schemas.topic import TopicRef


class AuthorRef(BaseModel):
    """An author as listed on a publication."""

    researcher_id: int | None = None
    full_name: str
    order: int = 1


class Publication(BaseModel):
    """A research output (journal/conference/book)."""

    publication_id: int
    title: str
    abstract: str = ""
    doi: str | None = None
    publication_year: int
    journal_name: str = ""
    publication_type: str = "journal"
    citation_count: int = 0
    campus: str = ""
    authors: list[AuthorRef] = []
    topics: list[TopicRef] = []
    source: str = "sample"


class PublicationRef(BaseModel):
    """Compact publication reference for profile listings."""

    publication_id: int
    title: str
    publication_year: int
    journal_name: str = ""
    citation_count: int = 0
    doi: str | None = None
