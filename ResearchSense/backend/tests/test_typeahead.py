"""Suggestions appear while typing, drawn from the same search as results."""

import time

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _get(**params):
    r = client.get("/api/suggest", params=params)
    assert r.status_code == 200
    return r.json()


def test_three_letters_find_the_person():
    people = [s["label"] for s in _get(q="ari", scope="researchers")]
    assert "Arif Ur Rahman" in people


def test_full_profiles_come_before_name_only_authors():
    first = _get(q="arif", scope="researchers")[0]
    assert first["label"] == "Arif Ur Rahman"
    assert "Computer Science" in first["detail"]


def test_one_letter_suggests_nothing():
    assert _get(q="a") == []


def test_all_scopes_are_labelled():
    kinds = {s["kind"] for s in _get(q="machine learning")}
    assert kinds == {"researcher", "topic", "publication"}


def test_scope_limits_the_kinds():
    assert {s["kind"] for s in _get(q="energy", scope="topics")} == {"topic"}


def test_limit_is_respected_per_kind():
    rows = _get(q="data", scope="publications", limit=3)
    assert len(rows) == 3


def test_fast_enough_to_run_per_keystroke():
    _get(q="warm")  # indexes are built once
    start = time.perf_counter()
    for q in ("ma", "mac", "mach", "machi", "machin"):
        _get(q=q)
    assert (time.perf_counter() - start) / 5 < 0.25
