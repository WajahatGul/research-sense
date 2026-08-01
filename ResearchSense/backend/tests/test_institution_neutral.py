"""The API must report the configured institution, never a value baked into
the seed data — so ResearchSense stays institution-agnostic (product-only)."""

from __future__ import annotations

from app.core.config import settings
from app.schemas.researcher import Researcher, ResearcherDetail

_BASE = {
    "researcher_id": 1,
    "full_name": "Alice Khan",
    "designation": "Professor",
    "department": "Computer Science",
}


def test_seed_institution_is_replaced_by_config():
    r = Researcher(**_BASE, institution="Bahria University")
    assert r.institution == settings.institution_name


def test_detail_inherits_neutralisation():
    r = ResearcherDetail(**_BASE, institution="Some Other University")
    assert r.institution == settings.institution_name


def test_configured_institution_is_honoured(monkeypatch):
    monkeypatch.setattr(settings, "institution_name", "Meridian University")
    r = Researcher(**_BASE, institution="Bahria University")
    assert r.institution == "Meridian University"
