"""People hear what was decided about their claim, paper or correction."""

import json

import pytest
from fastapi.testclient import TestClient

from app.core import throttle
from app.core.deps import get_auth_service
from app.repositories.accounts import AccountStore
from app.services import auth_service, notify_service

ARIF = 8  # Arif Ur Rahman
ARIF_EMAIL = "arif.buic@bahria.edu.pk"


@pytest.fixture()
def client(monkeypatch):
    for name in ("SMTP_HOST", "SMTP_USER", "SMTP_PASSWORD", "SMTP_FROM"):
        monkeypatch.delenv(name, raising=False)
    throttle.reset()
    get_auth_service.cache_clear()
    monkeypatch.setattr(auth_service, "verify_claim", lambda orcid, name: [name])
    monkeypatch.setattr(auth_service, "fetch_record_employers", lambda orcid: [])
    from app.core import security
    from app.main import app

    app.dependency_overrides[security.current_admin] = lambda: {
        "sub": "admin",
        "role": "admin",
    }
    yield TestClient(app)
    app.dependency_overrides.clear()


def _pending_claim(client) -> int:
    client.post(
        "/api/auth/claim",
        json={
            "researcher_id": ARIF,
            "orcid_id": "0000-0001-8239-2033",
            "password": "a-password-1",
        },
    )
    return client.get("/api/admin/claims").json()[0]["id"]


def test_an_approved_claim_tells_the_profile_owner(client):
    client.post(f"/api/admin/claims/{_pending_claim(client)}/approve")
    [m] = notify_service.recent()
    assert m["to_addr"] == ARIF_EMAIL
    assert m["subject"] == "Your ResearchSense profile is yours"
    assert "Dear Arif Ur Rahman" in m["body"] and "/portal" in m["body"]
    # Sent to the directory address, so an impostor's approval reaches the real owner.
    assert "If you did not claim this profile" in m["body"]
    # No mail server set: kept for an admin to read, marked as not sent.
    assert m["status"] == "not sent"


def test_a_rejection_carries_the_reviewers_reason(client):
    claim = _pending_claim(client)
    client.post(
        f"/api/admin/claims/{claim}/reject", json={"note": "Not on the staff list"}
    )
    [m] = notify_service.recent()
    assert "was not approved" in m["body"] and "Not on the staff list" in m["body"]


def test_paper_decisions_are_sent(client):
    store = AccountStore.instance()
    sub = store.create_submission(
        "publication", ARIF, "Edge caching for rural clinics", "{}"
    )
    client.post(
        f"/api/admin/papers/{sub}/reject",
        json={"note": "Duplicate of an existing record"},
    )
    [m] = notify_service.recent()
    assert m["subject"] == "About the paper you sent to ResearchSense"
    assert "“Edge caching for rural clinics” was not added" in m["body"]
    assert "Duplicate of an existing record" in m["body"]


def test_correction_decisions_name_what_was_asked():
    payload = {"paper": {"title": "A paper that is not mine"}}
    notify_service.correction_decided(
        {
            "id": 5,
            "kind": "not_author",
            "researcher_id": ARIF,
            "payload_json": json.dumps(payload),
        },
        approved=True,
    )
    [m] = notify_service.recent()
    assert m["subject"] == "Your record has been corrected"
    assert "not yours (“A paper that is not mine”)" in m["body"]


class _FakeSMTP:
    sent: list = []
    fail = False

    def __init__(self, host, port, timeout):
        self.host = host

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def starttls(self):
        pass

    def login(self, user, password):
        if self.fail:
            raise OSError("authentication refused")

    def send_message(self, message):
        self.sent.append(message)


@pytest.fixture()
def mail_server(monkeypatch):
    monkeypatch.setenv("SMTP_HOST", "smtp.example.org")
    monkeypatch.setenv("SMTP_USER", "portal@example.org")
    monkeypatch.setenv("SMTP_PASSWORD", "x")
    monkeypatch.setattr(notify_service.smtplib, "SMTP", _FakeSMTP)
    _FakeSMTP.sent, _FakeSMTP.fail = [], False

    # Deliver in the test's own thread so the result can be checked.
    class _Now:
        def __init__(self, target, args, daemon):
            self.target, self.args = target, args

        def start(self):
            self.target(*self.args)

    monkeypatch.setattr(notify_service.threading, "Thread", _Now)
    return _FakeSMTP


def test_with_a_mail_server_the_message_is_sent(client, mail_server):
    client.post(f"/api/admin/claims/{_pending_claim(client)}/approve")
    [message] = mail_server.sent
    assert message["To"] == ARIF_EMAIL and message["From"] == "portal@example.org"
    assert notify_service.recent()[0]["status"] == "sent"


def test_a_mail_failure_is_recorded_and_the_decision_still_stands(client, mail_server):
    mail_server.fail = True
    r = client.post(f"/api/admin/claims/{_pending_claim(client)}/approve")
    assert r.status_code == 200 and r.json()["status"] == "approved"
    m = notify_service.recent()[0]
    assert m["status"] == "failed" and "authentication refused" in m["error"]


def test_the_outbox_is_for_admins_only():
    from app.main import app

    assert TestClient(app).get("/api/admin/outbox").status_code == 401
