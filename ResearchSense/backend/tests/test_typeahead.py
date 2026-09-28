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
    kinds = {s["kind"] for s in _get(q="machine learning", limit=10)}
    assert kinds == {"researcher", "topic", "publication"}


def test_the_best_match_comes_first_whatever_its_kind():
    # People who match only through their research areas used to come
    # first; the area whose name is what was typed belongs on top.
    first = _get(q="machine learning", limit=8)[0]
    assert (first["kind"], first["label"]) == ("topic", "Machine Learning")
    assert _get(q="machine", limit=8)[0]["kind"] != "researcher"


def test_a_topic_search_still_offers_people():
    kinds = [s["kind"] for s in _get(q="machine learning", limit=8)]
    assert "researcher" in kinds


def test_a_name_still_puts_the_person_first():
    first = _get(q="arif ur rahman", limit=8)[0]
    assert (first["kind"], first["label"]) == ("researcher", "Arif Ur Rahman")


def test_a_mixed_list_respects_the_total_limit():
    assert len(_get(q="data", limit=8)) == 8


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


def test_areas_can_be_narrowed_to_a_department():
    everything = client.get("/api/topics").json()
    cs = client.get("/api/topics", params={"department": "Computer Science"}).json()
    assert 0 < len(cs) < len(everything)
    assert "Topic Modeling" in {t["topic_name"] for t in cs}


def test_areas_are_filed_under_broad_fields():
    rows = client.get("/api/topics").json()
    assert sum(1 for t in rows if t["field"]) / len(rows) > 0.95
    modeling = next(t for t in rows if t["topic_name"] == "Topic Modeling")
    assert (modeling["field"], modeling["field_source"]) == ("Computer Science", "openalex")


def test_areas_can_be_narrowed_to_a_field():
    cs = client.get("/api/topics", params={"field": "Computer Science"}).json()
    assert cs and all(t["field"] == "Computer Science" for t in cs)
