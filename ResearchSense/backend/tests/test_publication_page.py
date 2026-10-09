"""A paper has a page of its own, with the papers to read next."""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_a_paper_can_be_opened_by_id():
    r = client.get("/api/publications/5371")
    assert r.status_code == 200
    assert r.json()["title"] == "Database Preservation: The DBPreserve Approach"


def test_related_papers_share_a_subject_or_an_author():
    me = client.get("/api/publications/5371").json()
    areas = set(me["topic_names"])
    people = {a["researcher_id"] for a in me["authors"] if a["researcher_id"]}
    related = client.get("/api/publications/5371/related").json()
    assert 0 < len(related) <= 5
    for p in related:
        assert p["publication_id"] != 5371
        assert areas & set(p["topic_names"]) or people & {
            a["researcher_id"] for a in p["authors"]
        }


def test_related_for_a_missing_paper_is_404():
    assert client.get("/api/publications/999999/related").status_code == 404
