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
        "publication", 1, title, json.dumps({"title": title, "authors": []}))


def test_pending_queue_lists_submissions(client):
    _pend("Queued Paper")
    rows = client.get("/api/admin/papers/pending").json()
    assert [r["title"] for r in rows] == ["Queued Paper"]
    assert rows[0]["record"]["title"] == "Queued Paper"


def test_approve_publishes_and_merges(client, monkeypatch):
    import app.routers.admin as admin_mod
    published, merged = [], []
    monkeypatch.setattr(admin_mod.submission_service, "publish_record",
                        lambda rec: published.append(rec) or {**rec, "publication_id": 99})
    monkeypatch.setattr(admin_mod.staging, "merge_staged",
                        lambda sid: merged.append(sid) or 1)
    sid = _pend()
    resp = client.post(f"/api/admin/papers/{sid}/approve")
    assert resp.status_code == 200
    assert published and merged == [sid]
    assert AccountStore.instance().get_submission(sid)["status"] == "approved"


def test_approve_is_idempotent(client, monkeypatch):
    import app.routers.admin as admin_mod
    monkeypatch.setattr(admin_mod.submission_service, "publish_record",
                        lambda rec: {**rec, "publication_id": 1})
    monkeypatch.setattr(admin_mod.staging, "merge_staged", lambda sid: 1)
    sid = _pend()
    client.post(f"/api/admin/papers/{sid}/approve")
    resp = client.post(f"/api/admin/papers/{sid}/approve")
    assert resp.status_code == 200 and resp.json()["status"] == "approved"


def test_reject_discards_staged(client, monkeypatch):
    import app.routers.admin as admin_mod
    discarded = []
    monkeypatch.setattr(admin_mod.staging, "discard_staged",
                        lambda sid: discarded.append(sid))
    sid = _pend()
    resp = client.post(f"/api/admin/papers/{sid}/reject",
                       json={"note": "duplicate"})
    assert resp.status_code == 200
    assert discarded == [sid]
    sub = AccountStore.instance().get_submission(sid)
    assert sub["status"] == "rejected" and sub["note"] == "duplicate"


def test_upload_kind_approval_merges_without_publishing(client, monkeypatch):
    import app.routers.admin as admin_mod
    published, merged = [], []
    monkeypatch.setattr(admin_mod.submission_service, "publish_record",
                        lambda rec: published.append(rec))
    monkeypatch.setattr(admin_mod.staging, "merge_staged",
                        lambda sid: merged.append(sid) or 3)
    sid = AccountStore.instance().create_submission(
        "upload", 2, "PDF Paper", json.dumps({"filename": "f.pdf"}))
    client.post(f"/api/admin/papers/{sid}/approve")
    assert merged == [sid] and not published
