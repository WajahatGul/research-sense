"""Research project and funding schemas."""
from __future__ import annotations

from pydantic import BaseModel


class Funding(BaseModel):
    """A funding source attached to a project."""

    funding_id: int
    agency_name: str
    country: str = "Pakistan"
    amount: float = 0.0
    currency: str = "PKR"


class Project(BaseModel):
    """A research project led by a principal investigator."""

    project_id: int
    project_title: str
    description: str = ""
    start_date: str
    end_date: str | None = None
    status: str = "ongoing"
    principal_investigator_id: int | None = None
    principal_investigator_name: str = ""
    department: str = ""
    campus: str = ""
    funding: list[Funding] = []
    topics: list[str] = []
    source: str = "sample"
