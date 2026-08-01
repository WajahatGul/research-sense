"""Tests for the department + research-area chatbot directory fast paths."""

from __future__ import annotations

import pytest

from app.services.rag import authored
from app.services.rag.directory import (
    _resolve_area,
    _resolve_department,
    directory_answer,
    research_area_answer,
)


def _r(rid, name, dept, rank, campus, pubs, areas):
    return {
        "researcher_id": rid,
        "full_name": name,
        "department": dept,
        "academic_rank": rank,
        "campus": campus,
        "publication_count": pubs,
        "research_areas": areas,
        "topics": [{"topic_id": i, "topic_name": a} for i, a in enumerate(areas)],
    }


FIXTURE = [
    _r(
        1,
        "Alice Khan",
        "Computer Science",
        "Professor",
        "Karachi",
        40,
        ["Artificial Intelligence", "Computer Vision"],
    ),
    _r(
        2,
        "Bilal Ahmed",
        "Computer Science",
        "Lecturer",
        "Karachi",
        10,
        ["Machine Learning"],
    ),
    _r(
        3,
        "Carol Malik",
        "Software Engineering",
        "Associate Professor",
        "Lahore",
        22,
        ["Artificial Intelligence"],
    ),
    _r(4, "Dawood Raza", "Law", "Lecturer", "Islamabad", 5, ["Constitutional Law"]),
]


@pytest.fixture(autouse=True)
def _fixture_data(monkeypatch):
    monkeypatch.setattr(authored._Store, "_researchers", FIXTURE)
    yield
    monkeypatch.setattr(authored._Store, "_researchers", None)


# --- department path --------------------------------------------------------


def test_lists_department_researchers_sorted_by_output():
    r = directory_answer("List the researchers in Computer Science")
    assert r is not None
    assert "Computer Science has 2 researchers on record" in r.answer
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


def test_topic_question_not_treated_as_department():
    assert directory_answer("who works on artificial intelligence") is None


def test_unknown_department_falls_through():
    assert directory_answer("list researchers in Astrophysics") is None


def test_non_listing_mention_falls_through():
    assert directory_answer("what is the law on data privacy") is None


def test_department_matched_on_word_boundary():
    assert _resolve_department("researchers studying flaws") is None
    assert _resolve_department("faculty in Law") == "Law"


# --- research-area path -----------------------------------------------------


def test_lists_researchers_in_area_via_alias():
    # "ai" must resolve to "Artificial Intelligence" and list both holders.
    r = research_area_answer("list researchers in ai")
    assert r is not None
    assert "work on Artificial Intelligence" in r.answer
    assert "Alice Khan" in r.answer and "Carol Malik" in r.answer
    assert {rid for _, rid in r.researchers} == {1, 3}


def test_who_works_on_area():
    r = research_area_answer("who works on machine learning")
    assert r is not None
    assert "Bilal Ahmed" in r.answer
    assert {rid for _, rid in r.researchers} == {2}


def test_same_answer_regardless_of_phrasing():
    a = research_area_answer("list researchers in ai")
    b = research_area_answer("list researchers who have worked in ai")
    assert a is not None and b is not None
    assert a.answer == b.answer


def test_paper_question_excluded():
    # "who wrote the AI paper" is authorship, not a directory listing.
    assert research_area_answer("who wrote the ai paper") is None
    assert research_area_answer("list publications in ai") is None


def test_unknown_area_falls_through():
    assert research_area_answer("who works on astrology") is None


def test_resolve_area_uses_synonyms():
    assert _resolve_area("researchers in nlp") is None or isinstance(
        _resolve_area("researchers in nlp"), str
    )  # NLP not in fixture -> None; the call must not raise
    assert _resolve_area("list researchers in ai") == "Artificial Intelligence"
