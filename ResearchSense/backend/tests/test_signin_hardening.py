"""Sign-in hardening: attempt throttling and stricter ORCID name matching.

Both come from QA findings on the running product: passwords could be guessed
without limit, and the name check was loose enough to let one researcher claim
a near-namesake's profile.
"""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from app.core import throttle
from app.services.orcid_service import _names_match

ACCOUNT = "0000-0002-1825-0097"


@pytest.fixture(autouse=True)
def clean_counters():
    throttle.reset()
    yield
    throttle.reset()


def test_wrong_passwords_lock_the_account():
    for _ in range(throttle.MAX_ATTEMPTS - 1):
        throttle.record_failure(ACCOUNT)
        throttle.check(ACCOUNT)  # still allowed

    throttle.record_failure(ACCOUNT)
    with pytest.raises(HTTPException) as exc:
        throttle.check(ACCOUNT)
    assert exc.value.status_code == 429
    assert "Retry-After" in exc.value.headers


def test_a_correct_password_clears_the_history():
    for _ in range(throttle.MAX_ATTEMPTS - 1):
        throttle.record_failure(ACCOUNT)
    throttle.record_success(ACCOUNT)

    # The near-miss is forgotten, so the next slip does not lock the account.
    throttle.record_failure(ACCOUNT)
    throttle.check(ACCOUNT)


def test_accounts_are_locked_independently():
    for _ in range(throttle.MAX_ATTEMPTS):
        throttle.record_failure(ACCOUNT)
    with pytest.raises(HTTPException):
        throttle.check(ACCOUNT)
    throttle.check("0000-0001-2345-6789")  # a different account is unaffected


def test_old_failures_expire(monkeypatch):
    """An occasional typo months apart must never add up to a lockout."""
    now = [1000.0]
    monkeypatch.setattr(throttle.time, "time", lambda: now[0])
    for _ in range(throttle.MAX_ATTEMPTS - 1):
        throttle.record_failure(ACCOUNT)

    now[0] += throttle.WINDOW_SECONDS + 1
    throttle.record_failure(ACCOUNT)  # starts a fresh window
    throttle.check(ACCOUNT)


# --- ORCID name matching ---------------------------------------------------
# The roster is full of Muhammad/Syed/Khan, so "two tokens in common" matched
# people who merely share the region's most common names.
@pytest.mark.parametrize(
    ("roster", "record"),
    [
        ("Muhammad Ali Khan", "Muhammad Usman Khan"),
        ("Syed Muhammad Usman", "Syed Muhammad Ahmed"),
        ("Arif Ur Rahman", "Arif Rahman Sheikh"),
        ("Ali Raza", "Ali Hassan"),
        ("Nadeem Sarwar", "Nadeem Akhtar"),
    ],
)
def test_a_near_namesake_cannot_claim_the_profile(roster, record):
    assert _names_match(roster, record) is False


@pytest.mark.parametrize(
    ("roster", "record"),
    [
        ("Nadeem Sarwar", "Nadeem Sarwar"),
        ("Sara Ahmed", "Sara J Ahmed"),  # middle initial on the ORCID record
        ("Dr Arif Ur Rahman", "Arif Ur Rehman"),  # title + transliteration
        ("Muhammad Asfand-e-Yar", "Muhammad Asfand e Yar"),  # punctuation
        ("Muhammad Saqib Sohail", "Saqib Sohail"),  # dropped first name
    ],
)
def test_the_real_person_still_matches(roster, record):
    assert _names_match(roster, record) is True
