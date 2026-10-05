"""Shared/generic schemas used across resources."""

from __future__ import annotations

from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class Paginated(BaseModel, Generic[T]):
    """Standard paginated envelope returned by list endpoints."""

    items: list[T]
    total: int
    page: int
    page_size: int
    #: When the query as typed found nothing, the corrected query whose
    #: results these are — so the UI can say "Showing results for …".
    corrected_query: str | None = None


class Stats(BaseModel):
    """Aggregate counters shown on the home page."""

    researchers: int
    #: Publication-only profiles, searchable by name but not listed in the
    #: directory. Zero for an institution workspace.
    researchers_extended: int = 0
    publications: int
    projects: int
    topics: int
    departments: int
    campuses: int
