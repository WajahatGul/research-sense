"""Submitting the same paper twice must not queue it twice.

A slow response invites a second click, and a researcher who is unsure the
first attempt worked will try again. Duplicate checks used to look only at
published papers, so both attempts entered the approval queue and an
admin had to notice and reject one by hand.
"""

import pytest

import app.repositories.accounts as accounts_mod
import app.services.submission_service as svc
from app.repositories.accounts import AccountStore

SUBMITTER = {"researcher_id": 1, "full_name": "A Researcher", "campus": "Karachi"}


@pytest.fixture()
def store(tmp_path, monkeypatch):
    monkeypatch.setattr(accounts_mod, "DB_PATH", tmp_path / "t.db")
    AccountStore._instance = None
    monkeypatch.setattr(svc, "_stage_submission", lambda sid, record: None)
    monkeypatch.setattr(
        svc,
        "_link_authors",
        lambda names, sub: [{"researcher_id": 1, "full_name": "A", "order": 1}],
    )
    yield AccountStore.instance()
    AccountStore._instance = None


def _manual(title="A Study Of Queue Behaviour"):
    return svc.submit_manual(title, "Journal X", 2025, "journal", SUBMITTER)


def test_resubmitting_a_pending_paper_is_refused(store):
    _manual()
    with pytest.raises(svc.SubmissionError, match="already waiting"):
        _manual()
    assert len(store.pending_submissions()) == 1


def test_the_pending_match_ignores_case_and_spacing(store):
    _manual("A Study Of Queue Behaviour")
    with pytest.raises(svc.SubmissionError):
        _manual("  a study of queue   BEHAVIOUR ")


def test_a_rejected_paper_can_be_submitted_again(store):
    first = _manual()
    store.set_submission_status(first["submission_id"], "rejected", "wrong venue")
    again = _manual()
    assert again["status"] == "pending"


def test_a_pending_doi_is_refused_even_with_a_new_title(store):
    meta = {
        "title": "Original Title",
        "publication_year": 2025,
        "journal_name": "J",
        "publication_type": "journal",
        "citation_count": 0,
        "abstract": "",
        "doi": "10.1234/abc.5678",
    }
    svc._create(meta, SUBMITTER, source="doi")
    assert svc.find_pending_duplicate("https://doi.org/10.1234/ABC.5678", "Other")
