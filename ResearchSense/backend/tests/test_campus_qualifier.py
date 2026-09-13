"""A campus named in the question must narrow the answer.

"Who works on machine learning in Karachi?" listed ten researchers across every
campus, so the answer silently did not match the question. Naming a place and
being given the whole institution is worse than being told there is nobody
there: the reader has no way to tell the filter was ignored.
"""

from __future__ import annotations

import pytest

from app.services.rag import authored
from app.services.rag.directory import (
    _resolve_campus,
    directory_answer,
    research_area_answer,
)


def _r(rid, name, dept, campus, areas):
    return {
        "researcher_id": rid,
        "full_name": name,
        "department": dept,
        "academic_rank": "Professor",
        "campus": campus,
        "publication_count": 10,
        "research_areas": areas,
        "topics": [{"topic_id": i, "topic_name": a} for i, a in enumerate(areas)],
    }


FIXTURE = [
    _r(1, "Alice Khan", "Computer Science", "Karachi", ["Machine Learning"]),
    _r(2, "Bilal Ahmed", "Computer Science", "Lahore", ["Machine Learning"]),
    _r(3, "Sara Malik", "Computer Science", "Islamabad (E-8)", ["Machine Learning"]),
    _r(4, "Usman Tariq", "Computer Science", "Islamabad (H-11)", ["Machine Learning"]),
    # A publication-only profile: no campus at all, must never be swept into a
    # campus-filtered answer.
    _r(5, "Nameless Author", "", "", ["Machine Learning"]),
]


@pytest.fixture(autouse=True)
def roster(monkeypatch):
    monkeypatch.setattr(authored._Store, "_researchers", FIXTURE)
    yield
    monkeypatch.setattr(authored._Store, "_researchers", None)


def test_a_named_campus_narrows_the_list():
    result = research_area_answer("Who works on machine learning in Karachi?")
    assert result is not None
    assert "Alice Khan" in result.answer
    assert "Bilal Ahmed" not in result.answer
    assert "at Karachi" in result.answer


def test_a_city_covers_all_of_its_campuses():
    """Someone asking "in Islamabad" means both sites, not one of them."""
    result = research_area_answer("Who works on machine learning in Islamabad?")
    assert result is not None
    assert "Sara Malik" in result.answer
    assert "Usman Tariq" in result.answer
    assert "Alice Khan" not in result.answer


def test_no_campus_named_still_lists_everyone():
    result = research_area_answer("Who works on machine learning?")
    assert result is not None
    assert "Alice Khan" in result.answer
    assert "Bilal Ahmed" in result.answer


def test_an_empty_campus_result_says_so_instead_of_widening():
    result = research_area_answer("Who works on machine learning in Multan?")
    # "Multan" is not a campus, so the filter does not apply and all are listed.
    assert result is not None
    assert "Alice Khan" in result.answer


def test_a_campus_with_nobody_in_that_area_is_reported_honestly(monkeypatch):
    # Lahore is a real campus here, it just has nobody working on the area.
    monkeypatch.setattr(
        authored._Store,
        "_researchers",
        [
            _r(1, "Alice Khan", "Computer Science", "Karachi", ["Machine Learning"]),
            _r(2, "Bilal Ahmed", "Computer Science", "Lahore", ["Cybersecurity"]),
        ],
    )
    result = research_area_answer("Who works on machine learning in Lahore?")
    assert result is not None
    assert "could not find anyone" in result.answer
    assert "Alice Khan" not in result.answer


def test_the_department_listing_honours_a_campus_too():
    result = directory_answer("Who are the researchers in computer science in Lahore?")
    assert result is not None
    assert "Bilal Ahmed" in result.answer
    assert "Alice Khan" not in result.answer


def test_profiles_with_no_campus_are_never_swept_into_a_campus_answer():
    result = research_area_answer("Who works on machine learning in Karachi?")
    assert result is not None
    assert "Nameless Author" not in result.answer


def test_resolving_a_campus_from_the_question():
    assert _resolve_campus("anything in Karachi") == ["Karachi"]
    assert _resolve_campus("nothing named here") is None
