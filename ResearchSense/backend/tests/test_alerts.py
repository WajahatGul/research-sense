"""Saved searches that email only new matches, and only once confirmed."""

import re

import pytest
from fastapi.testclient import TestClient

from app.services import alerts_service, notify_service

EMAIL = "reader@example.org"


@pytest.fixture()
def client():
    from app.main import app

    return TestClient(app)


def _token(message) -> str:
    return re.search(r"confirm=([\w-]+)", message["body"]).group(1)


def _keep(client, kind="publications", filters=None):
    return client.post(
        "/api/alerts",
        json={
            "email": EMAIL,
            "kind": kind,
            "filters": filters or {"q": "machine learning"},
        },
    )


def _pretend_new(monkeypatch, *extra):
    real = alerts_service.matches

    def with_new(kind, filters):
        return real(kind, filters) + [
            {"id": 900000 + i, "title": title, "detail": "Journal of Tests, 2026"}
            for i, title in enumerate(extra)
        ]

    monkeypatch.setattr(alerts_service, "matches", with_new)


def test_keeping_a_search_asks_the_address_to_confirm(client):
    r = _keep(client)
    assert r.status_code == 200 and r.json() == {"status": "check your email"}
    [m] = notify_service.recent()
    assert m["to_addr"] == EMAIL and m["subject"] == "Confirm your ResearchSense alert"
    assert "“machine learning”" in m["body"] and "/alerts?confirm=" in m["body"]
    assert "/alerts?stop=" in m["body"]


def test_nothing_is_sent_until_confirmed(client, monkeypatch):
    _keep(client)
    _pretend_new(monkeypatch, "A new paper")
    assert alerts_service.run_all() == 0


def test_only_new_matches_are_sent_and_only_once(client, monkeypatch):
    _keep(client)
    token = _token(notify_service.recent()[0])
    assert (
        client.post("/api/alerts/confirm", json={"token": token}).json()["status"]
        == "confirmed"
    )
    # What the search already found when it was kept is not news.
    assert alerts_service.run_all() == 0

    _pretend_new(monkeypatch, "Learning to cache at the edge")
    assert alerts_service.run_all() == 1
    m = notify_service.recent()[0]
    assert m["subject"].startswith("1 new on ResearchSense")
    assert "Learning to cache at the edge (Journal of Tests, 2026)" in m["body"]
    assert "/publications/900000" in m["body"] and "/alerts?stop=" in m["body"]
    # The same paper is not sent twice.
    assert alerts_service.run_all() == 0


def test_a_stopped_alert_sends_nothing(client, monkeypatch):
    _keep(client)
    token = _token(notify_service.recent()[0])
    client.post("/api/alerts/confirm", json={"token": token})
    assert (
        client.post("/api/alerts/stop", json={"token": token}).json()["status"]
        == "stopped"
    )
    _pretend_new(monkeypatch, "Another paper")
    assert alerts_service.run_all() == 0
    assert client.post("/api/alerts/confirm", json={"token": token}).status_code == 404


def test_researcher_alerts_follow_the_directory(client, monkeypatch):
    r = _keep(client, "researchers", {"department": "Computer Science"})
    assert r.status_code == 200
    client.post(
        "/api/alerts/confirm", json={"token": _token(notify_service.recent()[0])}
    )
    _pretend_new(monkeypatch, "Dr New Colleague")
    assert alerts_service.run_all() == 1
    assert "/researchers/900000" in notify_service.recent()[0]["body"]


@pytest.mark.parametrize(
    "body, message",
    [
        (
            {"email": "not-an-address", "kind": "publications", "filters": {"q": "x"}},
            "valid email",
        ),
        (
            {"email": EMAIL, "kind": "publications", "filters": {}},
            "Search or choose a filter",
        ),
        (
            {"email": EMAIL, "kind": "publications", "filters": {"password": "x"}},
            "Unknown filter",
        ),
        (
            {"email": EMAIL, "kind": "accounts", "filters": {"q": "x"}},
            "publications or researchers",
        ),
    ],
)
def test_bad_alerts_are_refused_plainly(client, body, message):
    r = client.post("/api/alerts", json=body)
    assert r.status_code == 422 and message in r.json()["detail"]


def test_an_address_cannot_be_flooded_with_confirmations(client):
    for q in ("one", "two", "three"):
        assert _keep(client, filters={"q": q}).status_code == 200
    r = _keep(client, filters={"q": "four"})
    assert (
        r.status_code == 422 and "Confirm the alerts already sent" in r.json()["detail"]
    )


def test_asking_again_resends_the_same_confirmation(client):
    _keep(client)
    _keep(client)
    first, second = notify_service.recent()
    assert _token(first) == _token(second)
