import json

import pytest

import app.repositories.accounts as accounts_mod
import app.services.submission_service as svc
from app.repositories.accounts import AccountStore


@pytest.fixture()
def store(tmp_path, monkeypatch):
    monkeypatch.setattr(accounts_mod, "DB_PATH", tmp_path / "t.db")
    AccountStore._instance = None
    yield AccountStore.instance()
    AccountStore._instance = None


def test_create_stages_instead_of_publishing(store, monkeypatch):
    staged = {}
    monkeypatch.setattr(
        svc, "_stage_submission", lambda sid, record: staged.setdefault(sid, record)
    )
    published = []
    monkeypatch.setattr(svc, "publish_record", lambda record: published.append(record))
    monkeypatch.setattr(
        svc,
        "_link_authors",
        lambda names, sub: [{"researcher_id": 1, "full_name": "A", "order": 1}],
    )
    meta = {
        "title": "Pending Paper",
        "publication_year": 2024,
        "journal_name": "J",
        "publication_type": "journal",
        "citation_count": 0,
        "abstract": "",
        "doi": None,
    }
    result = svc._create(
        meta,
        {"researcher_id": 1, "full_name": "A", "campus": "Karachi"},
        source="manual",
    )
    assert result["status"] == "pending"
    assert staged and not published
    sub = store.get_submission(result["submission_id"])
    assert sub["status"] == "pending"
    assert json.loads(sub["record_json"])["title"] == "Pending Paper"
