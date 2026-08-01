"""Tests for the department-directory chatbot fast path."""

from __future__ import annotations

import pytest

from app.services.rag import authored
from app.services.rag.directory import _resolve_department, directory_answer

FIXTURE = [
    {
        "researcher_id": 1,
        "full_name": "Alice Khan",
        "department": "Computer Science",
        "academic_rank": "Professor",
        "campus": "Karachi",
        "publication_count": 40,
    },
    {
        "researcher_id": 2,
        "full_name": "Bilal Ahmed",
        "department": "Computer Science",
        "academic_rank": "Lecturer",
        "campus": "Karachi",
        "publication_count": 10,
    },
    {
        "researcher_id": 3,
        "full_name": "Carol Malik",
        "department": "Software Engineering",
        "academic_rank": "Associate Professor",
        "campus": "Lahore",
        "publication_count": 22,
    },
    {
        "researcher_id": 4,
        "full_name": "Dawood Raza",
        "department": "Law",
        "academic_rank": "Lecturer",
        "campus": "Islamabad",
        "publication_count": 5,
    },
]


@pytest.fixture(autouse=True)
def _fixture_data(monkeypatch):
    monkeypatch.setattr(authored._Store, "_researchers", FIXTURE)
    yield
    monkeypatch.setattr(authored._Store, "_researchers", None)


def test_lists_department_researchers_sorted_by_output():
    r = directory_answer("List the researchers in Computer Science")
    assert r is not None
    assert "Computer Science has 2 researchers on record" in r.answer
    assert "Alice Khan" in r.answer and "Bilal Ahmed" in r.answer
    # most-published first
    assert r.answer.index("Alice Khan") < r.answer.index("Bilal Ahmed")
    assert {rid for _, rid in r.researchers} == {1, 2}


def test_who_works_in_department():
    r = directory_answer("Who works in the Software Engineering department?")
    assert r is not None
    assert "Carol Malik" in r.answer


def test_alias_resolves_cs():
    r = directory_answer("show me the faculty in CS")
    assert r is not None
    assert "Computer Science" in r.answer


def test_topic_question_falls_through_to_rag():
    # "works on <topic>" is a topic query, not a directory listing.
    assert directory_answer("Who works on machine learning?") is None
    assert directory_answer("who works on AI in Computer Science") is None


def test_unknown_department_falls_through():
    assert directory_answer("list researchers in Astrophysics") is None


def test_non_listing_mention_falls_through():
    # Names a department word but is not a people/listing question.
    assert directory_answer("what is the law on data privacy") is None


def test_department_matched_on_word_boundary():
    # 'law' must not match inside 'flaws'.
    assert _resolve_department("researchers studying flaws") is None
    assert _resolve_department("faculty in Law") == "Law"
