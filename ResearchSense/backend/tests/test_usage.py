"""Measurement: searches that find nothing, claims started vs finished,
and returning visitors."""

import sqlite3

import pytest
from fastapi.testclient import TestClient

import app.repositories.accounts as accounts_mod
from app.core import throttle
from app.core.deps import get_auth_service
from app.repositories.accounts import AccountStore

VISITOR = "3f1c9a2e-0b7d-4e61-9d2a-5c8e7f6a1b2c"


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(accounts_mod, "DB_PATH", tmp_path / "t.db")
    monkeypatch.setenv("ADMIN_USERNAME", "admin")
    monkeypatch.setenv("ADMIN_PASSWORD", "admin123")
    AccountStore._instance = None
    get_auth_service.cache_clear()
    throttle.reset()
    from app.main import app

    yield TestClient(app)
    AccountStore._instance = None
    get_auth_service.cache_clear()


def _usage(client):
    r = client.post(
        "/api/auth/admin-login", json={"username": "admin", "password": "admin123"}
    )
    return client.get(
        "/api/admin/usage", headers={"Authorization": f"Bearer {r.json()['token']}"}
    ).json()


def test_a_search_that_finds_nothing_is_counted_with_its_words(client):
    client.get("/api/researchers", params={"q": "Zqxwv Nonexistent"})
    client.get("/api/researchers", params={"q": "zqxwv   nonexistent"})
    client.get("/api/publications", params={"q": "zqxwv"})
    u = _usage(client)
    assert u["searches_without_results"] == 3
    assert u["top_missed_searches"][0] == {
        "query": "zqxwv nonexistent",
        "where": "researchers",
        "times": 2,
    }


def test_a_search_shown_only_after_respelling_counts_as_a_miss(client):
    r = client.get("/api/researchers", params={"q": "astrobiology"})
    assert r.json()["corrected_query"]  # the results are for another word
    assert _usage(client)["top_missed_searches"][0]["query"] == "astrobiology"


def test_searches_that_find_something_or_are_only_filtered_are_not_counted(client):
    client.get("/api/researchers", params={"q": "a"})  # too short to mean anything
    client.get("/api/publications", params={"q": "learning"})
    client.get("/api/publications", params={"q": "learning", "year": 1901})
    assert _usage(client)["searches_without_results"] == 0


def test_visits_count_once_a_day_and_returning_means_another_day(client):
    for _ in range(3):
        assert (
            client.post(
                "/api/events", json={"kind": "visit", "visitor": VISITOR}
            ).status_code
            == 204
        )
    client.post("/api/events", json={"kind": "visit", "visitor": "another-visitor-1"})
    with sqlite3.connect(accounts_mod.DB_PATH) as con:
        assert (
            con.execute("SELECT COUNT(*) FROM events WHERE kind='visit'").fetchone()[0]
            == 2
        )
        # The first visitor also came yesterday.
        con.execute(
            "INSERT INTO events (at, day, kind, visitor) VALUES"
            " (date('now','-1 day'), date('now','-1 day'), 'visit', ?)",
            (VISITOR,),
        )
    u = _usage(client)
    assert u["visitors"] == 2 and u["returning_visitors"] == 1


def test_claims_started_against_sent_and_opened(client):
    for rid in ("8", "8", "9"):
        client.post(
            "/api/events",
            json={"kind": "claim_started", "visitor": VISITOR, "detail": rid},
        )
    AccountStore.instance().create_claim("0000-0000-0000-0001", 8, "h", "{}")
    assert _usage(client)["claims"] == {
        "started": 2,
        "sent_for_review": 1,
        "profiles_claimed": 0,
    }


def test_the_browser_can_only_report_known_events(client):
    assert (
        client.post(
            "/api/events", json={"kind": "search_empty:researchers", "visitor": VISITOR}
        ).status_code
        == 422
    )
    assert (
        client.post("/api/events", json={"kind": "visit", "visitor": "x"}).status_code
        == 422
    )
    assert client.get("/api/admin/usage").status_code == 401
