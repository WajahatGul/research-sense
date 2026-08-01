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


# --- FINDING 1: publish_record must never write to the RAG index itself ---
# (that would double-index the fact-card merge_staged already appended, and
# would defeat staging's whole point of making approval instant). Note the
# other approval tests monkeypatch publish_record wholesale, so they would
# never catch a regression here — these two do not.


def test_publish_record_has_no_index_writing_helper():
    """_index_chunk must be gone entirely: nothing else called it, and its
    only caller (publish_record) must not embed/write index files itself."""
    assert not hasattr(svc, "_index_chunk")


def test_publish_record_does_not_touch_rag_index(tmp_path, monkeypatch):
    monkeypatch.setattr(svc, "DATA_DIR", tmp_path)
    (tmp_path / "publications.json").write_text("[]", "utf-8")
    (tmp_path / "researchers.json").write_text("[]", "utf-8")
    monkeypatch.setattr(svc.loader, "clear_cache", lambda: None)

    record = {
        "title": "Approved Paper",
        "abstract": "",
        "doi": None,
        "publication_year": 2024,
        "journal_name": "J",
        "publication_type": "journal",
        "citation_count": 0,
        "campus": "Karachi",
        "authors": [],
        "topics": [],
        "source": "manual",
    }
    # No rag_chunks.json / rag_index.npz exist in tmp_path. If publish_record
    # tried to read or write them (the old bug), this would raise.
    result = svc.publish_record(record)
    assert result["publication_id"] == 1
    assert not (tmp_path / "rag_chunks.json").exists()
    assert not (tmp_path / "rag_index.npz").exists()
