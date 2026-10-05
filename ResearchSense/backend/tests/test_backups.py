"""Backups of the accounts database, and a restore that is tested first."""

import sqlite3

import pytest
from fastapi.testclient import TestClient

import app.repositories.accounts as accounts_mod
from app.core import throttle
from app.core.deps import get_auth_service
from app.repositories.accounts import AccountStore
from app.services import backup_service


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(accounts_mod, "DB_PATH", tmp_path / "t.db")
    monkeypatch.setenv("RS_BACKUP_DIR", str(tmp_path / "backups"))
    monkeypatch.setenv("ADMIN_USERNAME", "admin")
    monkeypatch.setenv("ADMIN_PASSWORD", "admin123")
    AccountStore._instance = None
    get_auth_service.cache_clear()
    throttle.reset()
    from app.main import app

    c = TestClient(app)
    r = c.post(
        "/api/auth/admin-login", json={"username": "admin", "password": "admin123"}
    )
    c.headers["Authorization"] = f"Bearer {r.json()['token']}"
    yield c
    AccountStore._instance = None
    get_auth_service.cache_clear()


def _claims() -> int:
    with sqlite3.connect(accounts_mod.DB_PATH) as con:
        return con.execute("SELECT COUNT(*) FROM claims").fetchone()[0]


def _add_claim(n: int = 1) -> None:
    for i in range(n):
        AccountStore.instance().create_claim(
            f"0000-0000-0000-{i:04d}", 100 + i, "h", "{}"
        )


def test_a_backup_is_checked_and_listed_with_its_contents(client):
    _add_claim(2)
    made = client.post("/api/admin/backups").json()
    assert made["counts"]["claims"] == 2
    listed = client.get("/api/admin/backups").json()["backups"]
    assert [b["name"] for b in listed] == [made["name"]]
    assert not list(backup_service.backup_dir().glob("*.partial"))


def test_restore_brings_back_lost_data_and_keeps_what_it_replaced(client):
    _add_claim(2)
    good = client.post("/api/admin/backups").json()["name"]
    with sqlite3.connect(accounts_mod.DB_PATH) as con:
        con.execute("DELETE FROM claims")  # the accident
    assert _claims() == 0

    r = client.post(f"/api/admin/backups/{good}/restore")
    assert r.status_code == 200, r.text
    assert _claims() == 2
    # The damaged state was itself kept, so the restore can be undone.
    previous = r.json()["previous"]
    assert previous.endswith("-before-restore.db")
    assert backup_service.inspect(backup_service.backup_dir() / previous)["claims"] == 0
    # And the restored log says who restored it.
    actions = [a["action"] for a in client.get("/api/admin/activity").json()]
    assert "backup.restored" in actions


def test_a_damaged_backup_is_refused_and_the_live_data_untouched(client):
    _add_claim(1)
    name = client.post("/api/admin/backups").json()["name"]
    (backup_service.backup_dir() / name).write_bytes(b"not a database at all" * 100)
    r = client.post(f"/api/admin/backups/{name}/restore")
    assert r.status_code == 400
    assert "Not restored" in r.json()["detail"]
    assert _claims() == 1


def test_only_backup_files_can_be_named(client):
    r = client.post("/api/admin/backups/..%2Ft.db/restore")
    assert r.status_code in (400, 404)
    assert client.post("/api/admin/backups/t.db/restore").status_code == 400


def test_old_backups_are_pruned(client, monkeypatch):
    folder = backup_service.backup_dir()
    folder.mkdir(parents=True)
    for day in range(1, 20):
        (folder / f"accounts-202601{day:02d}-000000.db").write_bytes(b"")
    backup_service.take()
    names = sorted(p.name for p in folder.glob("accounts-*.db"))
    assert len(names) == backup_service.KEEP
    assert "accounts-20260101-000000.db" not in names


def test_backups_need_an_admin(client):
    client.headers.pop("Authorization")
    assert client.get("/api/admin/backups").status_code == 401
