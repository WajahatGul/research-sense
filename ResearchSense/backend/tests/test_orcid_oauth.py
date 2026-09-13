"""Sign in with ORCID: proof of ownership, not just a name that matches.

The registry check can only confirm the name on a public ORCID record. iDs are
public, so a determined person could claim a colleague's profile — and in a
roster full of near-identical names even the honest path misfires. Signing in
at orcid.org settles it, because ORCID hands back the iD it issued the person
who just authenticated.
"""

from __future__ import annotations

import pytest

from app.core.config import settings
from app.services import orcid_oauth


@pytest.fixture(autouse=True)
def configured(monkeypatch):
    monkeypatch.setattr(settings, "orcid_client_id", "APP-TEST")
    monkeypatch.setattr(settings, "orcid_client_secret", "secret")
    monkeypatch.setattr(
        settings, "orcid_redirect_uri", "http://localhost:8000/api/auth/orcid/callback"
    )
    orcid_oauth.reset()
    yield
    orcid_oauth.reset()


def test_unconfigured_deployments_do_not_offer_it(monkeypatch):
    """The portal must fall back to the name check, not show a dead button."""
    monkeypatch.setattr(settings, "orcid_client_id", "")
    assert orcid_oauth.available() is False


def test_the_authorize_url_asks_only_to_authenticate():
    url = orcid_oauth.begin(7, "hunter2hunter2")
    assert url.startswith("https://orcid.org/oauth/authorize?")
    # The narrowest scope there is: identify the person, read nothing.
    assert "scope=%2Fauthenticate" in url
    assert "client_id=APP-TEST" in url
    assert "response_type=code" in url


def test_the_password_never_travels_through_the_browser():
    """It is held server-side against the state value, not put in the URL."""
    url = orcid_oauth.begin(7, "hunter2hunter2")
    assert "hunter2hunter2" not in url


def test_the_pending_claim_is_returned_once_only():
    """A replayed callback must not create a second account."""
    url = orcid_oauth.begin(7, "hunter2hunter2")
    state = url.split("state=")[1].split("&")[0]

    first = orcid_oauth.take_pending(state)
    assert first is not None
    assert first.researcher_id == 7
    assert first.password == "hunter2hunter2"

    assert orcid_oauth.take_pending(state) is None


def test_an_unknown_state_is_rejected():
    assert orcid_oauth.take_pending("not-a-real-state") is None


def test_an_abandoned_claim_expires(monkeypatch):
    url = orcid_oauth.begin(7, "hunter2hunter2")
    state = url.split("state=")[1].split("&")[0]

    later = [0.0]
    real_time = orcid_oauth.time.time

    def fake_time():
        return real_time() + later[0]

    monkeypatch.setattr(orcid_oauth.time, "time", fake_time)
    later[0] = orcid_oauth.PENDING_TTL_SECONDS + 1
    assert orcid_oauth.take_pending(state) is None


def test_the_sandbox_is_used_when_asked_for(monkeypatch):
    monkeypatch.setattr(settings, "orcid_sandbox", True)
    assert orcid_oauth.begin(1, "hunter2hunter2").startswith(
        "https://sandbox.orcid.org/"
    )


class _Resp:
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        return self._payload


def test_the_exchange_returns_the_authenticated_id(monkeypatch):
    monkeypatch.setattr(
        orcid_oauth.httpx,
        "post",
        lambda *a, **k: _Resp(200, {"orcid": "0000-0002-1825-0097"}),
    )
    assert orcid_oauth.exchange("code") == "0000-0002-1825-0097"


def test_a_refused_exchange_is_a_user_safe_error(monkeypatch):
    monkeypatch.setattr(
        orcid_oauth.httpx, "post", lambda *a, **k: _Resp(400, {"error": "bad"})
    )
    with pytest.raises(ValueError) as exc:
        orcid_oauth.exchange("code")
    # No secrets, no stack, nothing the reader cannot act on.
    assert "secret" not in str(exc.value).lower()
    assert "try again" in str(exc.value).lower()


def test_an_exchange_without_an_id_is_refused(monkeypatch):
    monkeypatch.setattr(orcid_oauth.httpx, "post", lambda *a, **k: _Resp(200, {}))
    with pytest.raises(ValueError):
        orcid_oauth.exchange("code")
