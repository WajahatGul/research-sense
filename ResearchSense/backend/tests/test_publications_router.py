from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_list_publications_accepts_valid_date_range():
    resp = client.get(
        "/api/publications", params={"date_from": "2020-01-01", "date_to": "2020-12-31"}
    )
    assert resp.status_code == 200


def test_list_publications_rejects_malformed_date_from():
    resp = client.get("/api/publications", params={"date_from": "2020/01/01"})
    assert resp.status_code == 422
    assert resp.json()["detail"] == "date_from must be YYYY-MM-DD"


def test_list_publications_rejects_malformed_date_to():
    resp = client.get("/api/publications", params={"date_to": "not-a-date"})
    assert resp.status_code == 422
    assert resp.json()["detail"] == "date_to must be YYYY-MM-DD"
