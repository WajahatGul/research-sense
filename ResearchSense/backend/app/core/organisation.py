"""What kind of organisation this deployment serves, and the words it uses.

ResearchSense started as a university portal, but the same idea (who knows
what, and what have they written) fits a company's R&D group, a defence
research establishment or a government agency. Those organisations call
things by different names: a university has departments and campuses and
publishes journal articles; a company has teams and sites and writes
white papers and patents.

``RS_ORG_KIND`` picks one of the profiles below. The name itself comes from
``RS_INSTITUTION_NAME`` (or a signed-up workspace) and is empty by default,
so an unconfigured deployment reads as a neutral product rather than as one
particular university.

Document types are the ones an organisation of that kind produces. Only the
types that actually have records are offered as filters: a "Patents" option
that always returns nothing is a dead end, not a feature. A type the data
holds but the profile does not name is still offered, under a readable label,
so an adapter can bring in new kinds of document without a code change.
"""

from __future__ import annotations

import os
from collections import Counter

from pydantic import BaseModel

from app.core.tenancy import institution_name
from app.repositories import loader

PROFILES: dict[str, dict] = {
    "education": {
        "noun": "institution",
        "people": "Researchers",
        "unit": "Department",
        "site": "Campus",
        "document_types": {
            "journal": "Journal article",
            "conference": "Conference paper",
            "book-chapter": "Book chapter",
            "book": "Book",
            "thesis": "Thesis",
            "preprint": "Preprint",
            "grant": "Grant",
            "report": "Technical report",
            "patent": "Patent",
            "dataset": "Dataset",
        },
    },
    "company": {
        "noun": "company",
        "people": "Experts",
        "unit": "Team",
        "site": "Site",
        "document_types": {
            "whitepaper": "White paper",
            "report": "Technical report",
            "patent": "Patent",
            "specification": "Specification",
            "case-study": "Case study",
            "journal": "Journal article",
            "conference": "Conference paper",
        },
    },
    "defence": {
        "noun": "organisation",
        "people": "Specialists",
        "unit": "Directorate",
        "site": "Establishment",
        "document_types": {
            "report": "Technical report",
            "trial-report": "Trial report",
            "specification": "Specification",
            "journal": "Journal article",
            "conference": "Conference paper",
            "patent": "Patent",
        },
    },
    "government": {
        "noun": "agency",
        "people": "Specialists",
        "unit": "Division",
        "site": "Office",
        "document_types": {
            "policy-brief": "Policy brief",
            "report": "Report",
            "guideline": "Guideline",
            "journal": "Journal article",
            "conference": "Conference paper",
        },
    },
}
DEFAULT_KIND = "education"


class DocumentType(BaseModel):
    key: str
    label: str
    count: int


class Organisation(BaseModel):
    name: str  # "" when unbranded
    kind: str
    noun: str  # "institution", "company", ...
    people: str
    unit: str
    site: str
    document_types: list[DocumentType]


def org_kind() -> str:
    kind = os.getenv("RS_ORG_KIND", DEFAULT_KIND).strip().lower()
    return kind if kind in PROFILES else DEFAULT_KIND


def _label(key: str) -> str:
    return key.replace("-", " ").replace("_", " ").capitalize()


def document_types(kind: str | None = None) -> list[DocumentType]:
    """Types present in the current workspace's records, most common first."""
    names = PROFILES[kind or org_kind()]["document_types"]
    counts = Counter(
        p.get("publication_type") or "journal" for p in loader.load("publications")
    )
    return [
        DocumentType(key=k, label=names.get(k, _label(k)), count=n)
        for k, n in counts.most_common()
    ]


def organisation() -> Organisation:
    kind = org_kind()
    p = PROFILES[kind]
    return Organisation(
        name=institution_name(),
        kind=kind,
        noun=p["noun"],
        people=p["people"],
        unit=p["unit"],
        site=p["site"],
        document_types=document_types(kind),
    )
