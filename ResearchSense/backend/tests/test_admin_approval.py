import json

import pytest
from fastapi.testclient import TestClient

import app.repositories.accounts as accounts_mod
from app.repositories.accounts import AccountStore


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(accounts_mod, "DB_PATH", tmp_path / "t.db")
    AccountStore._instance = None
    from app.core import security
    from app.main import app

    app.dependency_overrides[security.current_admin] = lambda: {"role": "admin"}
    yield TestClient(app)
    app.dependency_overrides.clear()
    AccountStore._instance = None


def _pend(title="P1"):
    return AccountStore.instance().create_submission(
        "publication", 1, title, json.dumps({"title": title, "authors": []})
    )


def test_pending_queue_lists_submissions(client):
    _pend("Queued Paper")
    rows = client.get("/api/admin/papers/pending").json()
    assert [r["title"] for r in rows] == ["Queued Paper"]
    assert rows[0]["record"]["title"] == "Queued Paper"


def test_approve_publishes_and_merges(client, monkeypatch):
    import app.routers.admin as admin_mod

    published, merged = [], []
    monkeypatch.setattr(
        admin_mod.submission_service,
        "publish_record",
        lambda rec: published.append(rec) or {**rec, "publication_id": 99},
    )
    monkeypatch.setattr(
        admin_mod.staging, "merge_staged", lambda sid: merged.append(sid) or 1
    )
    sid = _pend()
    resp = client.post(f"/api/admin/papers/{sid}/approve")
    assert resp.status_code == 200
    assert published and merged == [sid]
    assert AccountStore.instance().get_submission(sid)["status"] == "approved"


def test_approve_is_idempotent(client, monkeypatch):
    import app.routers.admin as admin_mod

    monkeypatch.setattr(
        admin_mod.submission_service,
        "publish_record",
        lambda rec: {**rec, "publication_id": 1},
    )
    monkeypatch.setattr(admin_mod.staging, "merge_staged", lambda sid: 1)
    sid = _pend()
    client.post(f"/api/admin/papers/{sid}/approve")
    resp = client.post(f"/api/admin/papers/{sid}/approve")
    assert resp.status_code == 200 and resp.json()["status"] == "approved"


def test_reject_discards_staged(client, monkeypatch):
    import app.routers.admin as admin_mod

    discarded = []
    monkeypatch.setattr(
        admin_mod.staging, "discard_staged", lambda sid: discarded.append(sid)
    )
    sid = _pend()
    resp = client.post(f"/api/admin/papers/{sid}/reject", json={"note": "duplicate"})
    assert resp.status_code == 200
    assert discarded == [sid]
    sub = AccountStore.instance().get_submission(sid)
    assert sub["status"] == "rejected" and sub["note"] == "duplicate"


def test_upload_kind_approval_merges_without_publishing(client, monkeypatch):
    import app.routers.admin as admin_mod

    published, merged = [], []
    monkeypatch.setattr(
        admin_mod.submission_service,
        "publish_record",
        lambda rec: published.append(rec),
    )
    monkeypatch.setattr(
        admin_mod.staging, "merge_staged", lambda sid: merged.append(sid) or 3
    )
    sid = AccountStore.instance().create_submission(
        "upload", 2, "PDF Paper", json.dumps({"filename": "f.pdf"})
    )
    client.post(f"/api/admin/papers/{sid}/approve")
    assert merged == [sid] and not published


def test_approve_publication_does_not_index_twice(client, monkeypatch):
    """FINDING 1: exercise the REAL publish_record (not monkeypatched away,
    unlike the other approval tests) so a regression that re-adds indexing
    inside publish_record would be caught. Only _persist/_bump_researcher_
    counts touch the filesystem here — merge_staged is spied to prove it (and
    only it) writes to the index, exactly once."""
    import app.services.submission_service as svc_mod

    published_records = []

    def fake_persist(record):
        published_records.append(record)
        return {**record, "publication_id": 7}

    monkeypatch.setattr(svc_mod, "_persist", fake_persist)
    monkeypatch.setattr(svc_mod, "_bump_researcher_counts", lambda record: None)

    import app.routers.admin as admin_mod

    merged = []
    monkeypatch.setattr(
        admin_mod.staging, "merge_staged", lambda sid: merged.append(sid) or 1
    )
    # publish_record must not have its own index-writing helper anymore —
    # merge_staged (spied above) is the only thing allowed to touch the index.
    assert not hasattr(svc_mod, "_index_chunk")

    sid = _pend("Real Publish Paper")
    resp = client.post(f"/api/admin/papers/{sid}/approve")

    assert resp.status_code == 200
    assert resp.json()["chunks_merged"] == 1
    assert published_records, "publish_record should have persisted the record"
    # merge_staged is the only thing that touched the index, exactly once.
    assert merged == [sid]


def test_approve_refuses_a_rejected_submission(client, monkeypatch):
    """FINDING 4: reject -> approve must not republish a paper whose staged
    vectors were already discarded."""
    import app.routers.admin as admin_mod

    monkeypatch.setattr(admin_mod.staging, "discard_staged", lambda sid: None)
    monkeypatch.setattr(admin_mod.staging, "merge_staged", lambda sid: 1)
    monkeypatch.setattr(admin_mod.submission_service, "publish_record", lambda rec: rec)

    sid = _pend("Reject Then Approve")
    reject_resp = client.post(
        f"/api/admin/papers/{sid}/reject", json={"note": "not relevant"}
    )
    assert reject_resp.status_code == 200

    approve_resp = client.post(f"/api/admin/papers/{sid}/approve")
    assert approve_resp.status_code == 409
    assert AccountStore.instance().get_submission(sid)["status"] == "rejected"


def test_reject_upload_deletes_pdf_file_and_uploads_row(client, tmp_path, monkeypatch):
    """FINDING 2/4: rejecting a PDF upload must delete both the stored file
    and its uploads-table row, so a later full index rebuild
    (scripts.build_index) can never pick it back up."""
    import app.routers.admin as admin_mod
    import app.routers.papers as papers_mod

    monkeypatch.setattr(papers_mod, "UPLOADS_DIR", tmp_path)
    (tmp_path / "f.pdf").write_bytes(b"%PDF-1.4 fake")
    monkeypatch.setattr(admin_mod.staging, "discard_staged", lambda sid: None)

    store = AccountStore.instance()
    sid = store.create_submission(
        "upload", 2, "PDF Paper", json.dumps({"filename": "f.pdf"})
    )
    store.record_upload(2, "PDF Paper", "f.pdf", submission_id=sid)

    resp = client.post(f"/api/admin/papers/{sid}/reject", json={"note": "n/a"})

    assert resp.status_code == 200
    assert not (tmp_path / "f.pdf").exists()
    assert store.approved_uploads() == []


def test_approve_logs_warning_on_zero_chunks_merged(client, monkeypatch, caplog):
    """FINDING 3: an approval that merges 0 staged chunks (e.g. staging
    silently failed at submission time) must log a warning, not fail
    silently — and the response must report the actual merged count."""
    import logging

    import app.routers.admin as admin_mod

    monkeypatch.setattr(admin_mod.staging, "merge_staged", lambda sid: 0)
    monkeypatch.setattr(admin_mod.submission_service, "publish_record", lambda rec: rec)

    sid = _pend("Zero Chunks Paper")
    with caplog.at_level(logging.WARNING, logger="app.routers.admin"):
        resp = client.post(f"/api/admin/papers/{sid}/approve")

    assert resp.status_code == 200
    assert resp.json()["chunks_merged"] == 0
    assert any("merged 0 staged chunks" in r.message for r in caplog.records)
