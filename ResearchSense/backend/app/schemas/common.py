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
