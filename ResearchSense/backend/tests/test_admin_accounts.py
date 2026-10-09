"""Named administrators, and a record of what each one did."""

import pytest
from fastapi.testclient import TestClient

import app.repositories.accounts as accounts_mod
from app.core import throttle
from app.core.deps import get_auth_service
from app.repositories.accounts import AccountStore

STRONG = "correct horse battery staple"


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(accounts_mod, "DB_PATH", tmp_path / "t.db")
    monkeypatch.setenv("ADMIN_USERNAME", "admin")
    monkeypatch.setenv("ADMIN_PASSWORD", "admin123")
    AccountStore._instance = None
    get_auth_service.cache_clear()
    throttle.reset()
    from app.main import app

    yield TestClient(app)
    AccountStore._instance = None
    get_auth_service.cache_clear()


def _login(client, username="admin", password="admin123"):
    r = client.post(
        "/api/auth/admin-login", json={"username": username, "password": password}
    )
    return r, {"Authorization": f"Bearer {r.json().get('token', '')}"}


def test_first_admin_comes_from_env_and_is_flagged_weak(client):
    r, h = _login(client)
    assert r.status_code == 200
    me = client.get("/api/auth/me", headers=h).json()
    assert me["full_name"] == "admin" and me["password_weak"] is True


def test_each_admin_signs_in_as_themselves(client):
    _, h = _login(client)
    assert (
        client.post(
            "/api/admin/admins",
            headers=h,
            json={"username": "sara", "password": STRONG},
        ).status_code
        == 200
    )
    r, h2 = _login(client, "sara", STRONG)
    assert r.status_code == 200
    assert client.get("/api/auth/me", headers=h2).json()["full_name"] == "sara"


def test_short_passwords_are_refused(client):
    _, h = _login(client)
    r = client.post(
        "/api/admin/admins", headers=h, json={"username": "bob", "password": "short"}
    )
    assert r.status_code == 400 and "12 characters" in r.json()["detail"]


def test_a_deactivated_admin_loses_access_at_once(client):
    _, h = _login(client)
    client.post(
        "/api/admin/admins", headers=h, json={"username": "sara", "password": STRONG}
    )
    _, sara = _login(client, "sara", STRONG)
    assert client.get("/api/admin/claims", headers=sara).status_code == 200
    client.post("/api/admin/admins/sara/active?active=false", headers=h)
    assert (
        client.get("/api/admin/claims", headers=sara).status_code == 401
    )  # same token
    assert _login(client, "sara", STRONG)[0].status_code == 401


def test_the_last_active_admin_cannot_be_removed(client):
    _, h = _login(client)
    r = client.post("/api/admin/admins/admin/active?active=false", headers=h)
    assert r.status_code == 400


def test_changing_the_password_clears_the_warning(client):
    _, h = _login(client)
    r = client.post(
        "/api/admin/password", headers=h, json={"current": "admin123", "new": STRONG}
    )
    assert r.status_code == 200
    assert _login(client)[0].status_code == 401
    r, h = _login(client, password=STRONG)
    assert client.get("/api/auth/me", headers=h).json()["password_weak"] is False


def test_every_decision_is_recorded_with_who_made_it(client):
    _login(client, password="wrong-password")
    _, h = _login(client)
    client.post(
        "/api/admin/admins", headers=h, json={"username": "sara", "password": STRONG}
    )
    client.post("/api/admin/admins/sara/active?active=false", headers=h)
    log = client.get("/api/admin/activity", headers=h).json()
    actions = [(e["actor"], e["action"], e["target"]) for e in log]
    assert ("admin", "admin.deactivated", "sara") in actions
    assert ("admin", "admin.created", "sara") in actions
    assert ("admin", "admin.login", "") in actions
    assert ("admin", "admin.login_failed", "") in actions


def test_the_log_cannot_be_edited_through_the_store():
    assert not any(
        name.startswith(("update_", "delete_", "clear_")) and "audit" in name
        for name in dir(AccountStore)
    )
