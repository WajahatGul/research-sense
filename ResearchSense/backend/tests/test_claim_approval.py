"""Claiming a profile by typing an ORCID iD waits for an administrator.

ORCID iDs are public, so before this anyone could type the real person's iD
with a password of their own and be signed in as them at once. Now such a
claim is held with the ORCID record's names and employers for an admin to
judge; only signing in at orcid.org goes live without review.
"""

import pytest
from fastapi.testclient import TestClient

import app.repositories.accounts as accounts_mod
from app.core import throttle
from app.core.deps import get_auth_service
from app.repositories.accounts import AccountStore
from app.services import auth_service

ARIF = 8  # Arif Ur Rahman
ARIF_ORCID = "0000-0001-8239-2033"
OTHER_ORCID = "0000-0002-1825-0097"


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(accounts_mod, "DB_PATH", tmp_path / "t.db")
    AccountStore._instance = None
    get_auth_service.cache_clear()  # it holds the store it was built with
    throttle.reset()
    # No network: the registry says the name matches, and lists an employer.
    monkeypatch.setattr(auth_service, "verify_claim", lambda orcid, name: [name])
    monkeypatch.setattr(
        auth_service, "fetch_record_employers", lambda orcid: ["Bahria University"]
    )
    from app.main import app

    yield TestClient(app)
    AccountStore._instance = None
    get_auth_service.cache_clear()


def _admin(client):
    from app.core import security
    from app.main import app

    app.dependency_overrides[security.current_admin] = lambda: {"role": "admin"}


def _claim(client, orcid=ARIF_ORCID, pw="a-password-1", rid=ARIF):
    return client.post(
        "/api/auth/claim",
        json={"researcher_id": rid, "orcid_id": orcid, "password": pw},
    )


def _login(client, orcid=ARIF_ORCID, pw="a-password-1"):
    return client.post("/api/auth/login", json={"orcid_id": orcid, "password": pw})


@pytest.fixture(autouse=True)
def _clear_overrides():
    yield
    from app.main import app

    app.dependency_overrides.clear()


def test_a_typed_claim_waits_and_gives_no_session(client):
    r = _claim(client)
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "pending"
    assert body["token"] is None
    assert ARIF not in client.get("/api/auth/claimed").json()


def test_signing_in_before_approval_says_it_is_waiting(client):
    _claim(client)
    r = _login(client)
    assert r.status_code == 403
    assert "waiting for an administrator" in r.json()["detail"]


def test_a_wrong_password_does_not_reveal_a_pending_claim(client):
    _claim(client)
    r = _login(client, pw="not-the-password")
    assert r.status_code == 401
    assert r.json()["detail"] == "Invalid ORCID iD or password"


def test_the_admin_sees_the_evidence_and_approves(client):
    _claim(client)
    _admin(client)
    [pending] = client.get("/api/admin/claims").json()
    assert pending["profile_name"] == "Arif Ur Rahman"
    assert pending["orcid_employers"] == ["Bahria University"]
    assert (
        client.post(f"/api/admin/claims/{pending['id']}/approve").json()["status"]
        == "approved"
    )
    assert client.get("/api/admin/claims").json() == []
    assert _login(client).status_code == 200
    assert ARIF in client.get("/api/auth/claimed").json()


def test_a_rejected_claim_says_why(client):
    _claim(client)
    _admin(client)
    [pending] = client.get("/api/admin/claims").json()
    client.post(
        f"/api/admin/claims/{pending['id']}/reject", json={"note": "Not on staff list"}
    )
    r = _login(client)
    assert r.status_code == 403
    assert "Not on staff list" in r.json()["detail"]


def test_a_false_claim_does_not_lock_out_the_real_owner(client):
    assert (
        _claim(client, orcid=OTHER_ORCID, pw="impostor-pw-1").json()["status"]
        == "pending"
    )
    assert _claim(client).json()["status"] == "pending"  # the owner can still claim
    _admin(client)
    claims = client.get("/api/admin/claims").json()
    assert {c["competing_claims"] for c in claims} == {1}
    real = next(c for c in claims if c["orcid_id"] == ARIF_ORCID)
    client.post(f"/api/admin/claims/{real['id']}/approve")
    # The competing claim was turned down with the approval.
    assert client.get("/api/admin/claims").json() == []
    assert _login(client, orcid=OTHER_ORCID, pw="impostor-pw-1").status_code == 403


def test_one_orcid_cannot_queue_two_claims(client):
    _claim(client)
    r = _claim(client, rid=9)
    assert r.status_code == 409


def test_orcid_sign_in_is_proof_and_goes_live_at_once(client):
    _claim(client, orcid=OTHER_ORCID, pw="impostor-pw-1")
    result = auth_service.AuthService(
        __import__(
            "app.repositories.mock.researchers", fromlist=["x"]
        ).MockResearcherRepository()
    ).claim_verified(ARIF, ARIF_ORCID, "a-password-1")
    assert result.status == "approved" and result.token
    _admin(client)
    assert client.get("/api/admin/claims").json() == []  # the impostor was turned down


def test_claim_endpoints_are_admin_only(client):
    assert client.get("/api/admin/claims").status_code in (401, 403)


def test_orcid_sign_in_on_someone_elses_profile_waits_for_review(client, monkeypatch):
    """Owning an ORCID iD does not make you the person on any profile you pick."""
    from app.services.orcid_service import OrcidVerificationError

    def mismatch(orcid, name):
        raise OrcidVerificationError("registered to someone else")

    monkeypatch.setattr(auth_service, "verify_claim", mismatch)
    monkeypatch.setattr(
        auth_service, "fetch_record_names", lambda orcid: ["Someone Else"]
    )
    service = auth_service.AuthService(
        __import__(
            "app.repositories.mock.researchers", fromlist=["x"]
        ).MockResearcherRepository()
    )
    result = service.claim_verified(ARIF, OTHER_ORCID, "a-password-1")
    assert result.status == "pending" and result.token is None
    _admin(client)
    [pending] = client.get("/api/admin/claims").json()
    assert pending["orcid_verified"] is True
    assert pending["orcid_names"] == ["Someone Else"]


def test_the_orcid_return_page_says_a_claim_is_waiting(client, monkeypatch):
    from app.services import orcid_oauth
    from app.services.orcid_service import OrcidVerificationError

    monkeypatch.setattr(
        auth_service,
        "verify_claim",
        lambda o, n: (_ for _ in ()).throw(OrcidVerificationError("x")),
    )
    monkeypatch.setattr(auth_service, "fetch_record_names", lambda orcid: [])
    monkeypatch.setattr(orcid_oauth, "exchange", lambda code: OTHER_ORCID)
    state = orcid_oauth.begin(ARIF, "a-password-1").split("state=")[1]
    r = client.get(
        "/api/auth/orcid/callback",
        params={"state": state, "code": "c"},
        follow_redirects=False,
    )
    assert r.status_code == 303 and "orcid_notice=" in r.headers["location"]
