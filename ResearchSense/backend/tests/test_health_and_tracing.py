"""Health must reflect what users get; every response must be traceable."""

from fastapi.testclient import TestClient

from app.core import health
from app.main import app

client = TestClient(app)


def test_health_is_ok_with_the_bundled_corpus():
    res = client.get("/api/health")
    assert res.status_code == 200
    body = res.json()
    assert body["corpus"]["ok"] is True
    assert body["corpus"]["researchers"] > 0
    assert body["corpus"]["publications"] > 0


def test_an_empty_corpus_fails_the_health_check(monkeypatch):
    # A deploy that cannot load its data must not pass and go live.
    monkeypatch.setattr(health.loader, "load", lambda name: [])
    res = client.get("/api/health")
    assert res.status_code == 503
    assert res.json()["status"] == "down"


def test_an_unreadable_corpus_fails_without_crashing_the_probe(monkeypatch):
    def broken(name):
        raise ValueError("corrupt json")

    monkeypatch.setattr(health.loader, "load", broken)
    res = client.get("/api/health")
    assert res.status_code == 503
    assert res.json()["corpus"] == {"ok": False, "error": "ValueError"}


def test_a_missing_assistant_index_is_degraded_not_down(monkeypatch, tmp_path):
    # The directory still works without the assistant's index, so the site
    # must stay up; the report says what is missing.
    monkeypatch.setattr(health.loader, "DATA_DIR", tmp_path)
    serving, report = health.check()
    assert serving is True
    assert report["status"] == "degraded"
    assert report["assistant_index"]["ok"] is False


def test_every_response_carries_a_request_id_and_timing():
    res = client.get("/api/stats")
    assert len(res.headers["X-Request-ID"]) == 12
    assert res.headers["Server-Timing"].startswith("app;dur=")


def test_a_well_formed_incoming_request_id_is_kept():
    res = client.get("/api/stats", headers={"X-Request-ID": "edge-7f3a"})
    assert res.headers["X-Request-ID"] == "edge-7f3a"


def test_a_malformed_request_id_is_replaced_not_echoed():
    res = client.get("/api/stats", headers={"X-Request-ID": "fake 200 GET /admin ok"})
    rid = res.headers["X-Request-ID"]
    assert " " not in rid and "admin" not in rid
