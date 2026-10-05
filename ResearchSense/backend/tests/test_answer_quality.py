"""Answers must match the question that was asked.

Each case here was found by putting real questions to the running assistant.
The pattern they share: the question carried a qualifier — a year, a subject,
a scope — and the answer quietly dropped it, returning something true but not
responsive. That is worse than refusing, because nothing signals the mismatch.
"""

from __future__ import annotations

import pytest

from app.services.rag import authored
from app.services.rag.leaderboard import leaderboard_answer
from app.services.rag.totals import totals_answer


def _r(rid, name, dept, campus, pubs, cites):
    return {
        "researcher_id": rid,
        "full_name": name,
        "department": dept,
        "academic_rank": "Professor",
        "campus": campus,
        "publication_count": pubs,
        "citation_count": cites,
        "research_areas": [],
        "topics": [],
        "source": "scraped",
    }


def _p(pid, title, year, rids, cites=0):
    return {
        "publication_id": pid,
        "title": title,
        "publication_year": year,
        "citation_count": cites,
        "journal_name": "IEEE Access",
        "authors": [
            {"researcher_id": r, "full_name": "x", "order": i + 1}
            for i, r in enumerate(rids)
        ],
    }


RESEARCHERS = [
    _r(1, "Nida Aman", "Accounting and Finance", "Islamabad (E-8)", 3, 50),
    _r(2, "Bilal Ahmed", "Computer Science", "Lahore", 2, 90),
]

PUBS = [
    _p(1, "Paper A", 2021, [1], 10),
    _p(2, "Paper B", 2023, [1], 20),
    _p(3, "Paper C", 2023, [1, 2], 20),
    _p(4, "Paper D", 2019, [2], 70),
]


@pytest.fixture(autouse=True)
def roster(monkeypatch):
    monkeypatch.setattr(authored._Store, "_researchers", RESEARCHERS)
    monkeypatch.setattr(authored._Store, "_pubs", PUBS)
    yield
    monkeypatch.setattr(authored._Store, "_researchers", None)
    monkeypatch.setattr(authored._Store, "_pubs", None)


# --- a year in the question --------------------------------------------
def test_a_named_year_narrows_the_publication_list():
    """Asking about 2023 used to return everything the author ever wrote."""
    result = authored.answer("What did Nida Aman publish in 2023?")
    assert result is not None
    assert "in 2023" in result.answer
    assert "Paper B" in result.answer and "Paper C" in result.answer
    assert "Paper A" not in result.answer


def test_a_year_range_is_honoured():
    result = authored.answer("What did Nida Aman publish between 2021 and 2023?")
    assert result is not None
    assert "Paper A" in result.answer
    assert "between 2021 and 2023" in result.answer


def test_a_year_with_nothing_in_it_says_so_rather_than_listing_everything():
    result = authored.answer("What did Nida Aman publish in 1990?")
    assert result is not None
    assert "no publications on record in 1990" in result.answer
    assert "Paper A" not in result.answer
    # Still says what there is, so the reader is not left at a dead end.
    assert "3 on record in total" in result.answer


def test_no_year_still_lists_everything():
    result = authored.answer("What papers has Nida Aman written?")
    assert result is not None
    for title in ("Paper A", "Paper B", "Paper C"):
        assert title in result.answer


# --- what the superlative is about --------------------------------------
def test_a_department_question_ranks_departments_not_people():
    """ "Which department has the most publications?" used to name a person."""
    result = leaderboard_answer("Which department has the most publications?")
    assert result is not None
    assert (
        "Accounting and Finance" in result.answer or "Computer Science" in result.answer
    )
    assert "Top departments by publications" in result.answer
    assert "Nida Aman" not in result.answer


def test_a_campus_question_ranks_campuses():
    result = leaderboard_answer("Which campus has the most citations?")
    assert result is not None
    assert "Top campuses by citations" in result.answer
    assert "campuss" not in result.answer  # naive pluralisation


def test_a_person_question_still_ranks_people():
    result = leaderboard_answer("Who has the most citations?")
    assert result is not None
    assert "Top researchers by citations" in result.answer


def test_a_paper_is_counted_once_per_department_not_per_author():
    """Paper C has an author in each department; summing per-researcher
    totals would count it twice for one of them."""
    result = leaderboard_answer("Which department has the most publications?")
    assert result is not None
    # Accounting has papers A, B, C = 3; Computer Science has C, D = 2.
    assert "Accounting and Finance - 3 publications" in result.answer


# --- counting the whole institution --------------------------------------
def test_how_many_publications_is_answered_not_refused(monkeypatch):
    """The most basic question a research portal gets used to dead-end."""
    from app.repositories import loader

    monkeypatch.setattr(
        loader,
        "load",
        lambda name: {"publications": PUBS, "researchers": RESEARCHERS}.get(name, []),
    )
    result = totals_answer("How many publications are there?")
    assert result is not None
    assert "4 publications" in result.answer


def test_a_count_about_one_person_is_left_to_the_authorship_path():
    assert totals_answer("How many papers has Nida Aman written?") is None


def test_a_question_that_is_not_counting_is_left_alone():
    assert totals_answer("What papers has Nida Aman written?") is None


# --- "who is X" when X is shared ---------------------------------------
AMBIGUOUS = [
    _r(1, "Arif Ur Rahman", "Computer Science", "Islamabad (E-8)", 40, 500),
    _r(2, "Muhammad Arif Khattak", "Mechanical", "Islamabad (E-8)", 20, 200),
    _r(3, "Zaeem Arif Butt", "Computer Science", "Lahore", 5, 30),
]


def test_a_shared_name_is_asked_about_not_guessed(monkeypatch):
    """Retrieval used to blend several people into one description of
    somebody who does not exist."""
    monkeypatch.setattr(authored._Store, "_researchers", AMBIGUOUS)
    result = authored.identity_answer("Who is Arif?")
    assert result is not None
    assert authored._DISAMBIGUATION_MARKER in result.answer
    for name in ("Arif Ur Rahman", "Muhammad Arif Khattak"):
        assert name in result.answer


def test_the_most_published_candidate_is_offered_first(monkeypatch):
    monkeypatch.setattr(authored._Store, "_researchers", AMBIGUOUS)
    result = authored.identity_answer("Who is Arif?")
    assert result is not None
    assert result.researchers[0][0] == "Arif Ur Rahman"


def test_one_clear_match_is_left_to_retrieval(monkeypatch):
    """A single match gets a far richer answer from the RAG pipeline."""
    monkeypatch.setattr(authored._Store, "_researchers", AMBIGUOUS)
    assert authored.identity_answer("Who is Zaeem Arif Butt?") is None


def test_an_authorship_question_is_not_hijacked(monkeypatch):
    monkeypatch.setattr(authored._Store, "_researchers", AMBIGUOUS)
    assert authored.identity_answer("What papers has Arif written?") is None


def test_naming_the_person_afterwards_answers_the_question(monkeypatch):
    """The follow-up only works if the marker survives in the question."""
    monkeypatch.setattr(authored._Store, "_researchers", AMBIGUOUS)
    monkeypatch.setattr(authored._Store, "_pubs", [_p(1, "Paper A", 2021, [1])])

    class Turn:
        role = "assistant"
        content = f"I found 3 researchers. {authored._DISAMBIGUATION_MARKER}"

    follow_up = authored.answer("Arif Ur Rahman", history=[Turn()])
    assert follow_up is not None
    assert "Paper A" in follow_up.answer
