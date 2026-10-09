"""The deployment describes itself: name, kind, vocabulary, document types."""

from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.organisation import document_types
from app.main import app

client = TestClient(app)


def test_unbranded_by_default():
    body = client.get("/api/organisation").json()
    assert body["name"] == ""
    assert body["kind"] == "education"
    assert body["unit"] == "Department"


def test_name_comes_from_configuration(monkeypatch):
    monkeypatch.setattr(settings, "institution_name", "Meridian University")
    assert client.get("/api/organisation").json()["name"] == "Meridian University"


def test_company_speaks_its_own_language(monkeypatch):
    monkeypatch.setenv("RS_ORG_KIND", "company")
    body = client.get("/api/organisation").json()
    assert (body["noun"], body["unit"], body["site"]) == ("company", "Team", "Site")


def test_unknown_kind_falls_back_to_education(monkeypatch):
    monkeypatch.setenv("RS_ORG_KIND", "spaceship")
    assert client.get("/api/organisation").json()["kind"] == "education"


def test_only_types_with_records_are_offered():
    types = {t.key: t for t in document_types("education")}
    assert types["journal"].label == "Journal article"
    assert types["book-chapter"].count > 0
    assert "patent" not in types  # named by the profile, but no records


def test_an_unnamed_type_still_gets_a_readable_label():
    # "book-chapter" is not in the company profile; an adapter bringing it
    # in should not need a code change to show it.
    types = {t.key: t.label for t in document_types("company")}
    assert types["book-chapter"] == "Book chapter"


def test_type_filter_matches_the_offered_keys():
    for t in document_types("education"):
        r = client.get(
            "/api/publications", params={"publication_type": t.key, "page_size": 1}
        )
        assert r.json()["total"] == t.count
