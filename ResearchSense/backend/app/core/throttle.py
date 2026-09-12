"""Failed-attempt throttling for the sign-in endpoints.

Without this, passwords can be guessed indefinitely: nothing slowed down or
stopped 12 wrong passwords fired in under four seconds. There is a second cost
too — every attempt runs 200,000 PBKDF2 iterations, so a burst of guesses is
also a cheap way to exhaust a small instance's CPU.

Counters are per account and live in memory: this runs as a single process, and
a restart clearing them is acceptable (an attacker cannot trigger one). Moving
to several workers means moving this into the database or a shared cache.
"""

from __future__ import annotations

import time

from fastapi import HTTPException

#: Wrong attempts allowed before the account stops accepting sign-ins.
MAX_ATTEMPTS = 5
#: Failures older than this are forgotten, so an occasional typo never locks.
WINDOW_SECONDS = 15 * 60
#: How long a locked account stays locked.
LOCKOUT_SECONDS = 15 * 60

# identity -> (failure count, first failure time, locked-until time)
_failures: dict[str, tuple[int, float, float]] = {}


def _key(identity: str) -> str:
    return identity.strip().lower()


def check(identity: str) -> None:
    """Raise 429 while this account is locked out."""
    count, first, locked_until = _failures.get(_key(identity), (0, 0.0, 0.0))
    remaining = locked_until - time.time()
    if remaining <= 0:
        return
    minutes = max(1, round(remaining / 60))
    raise HTTPException(
        status_code=429,
        detail=(
            f"Too many failed sign-in attempts. Try again in {minutes} minute"
            f"{'' if minutes == 1 else 's'}."
        ),
        headers={"Retry-After": str(int(remaining))},
    )


def record_failure(identity: str) -> None:
    """Count a wrong password, locking the account once the limit is reached."""
    key = _key(identity)
    now = time.time()
    count, first, locked_until = _failures.get(key, (0, now, 0.0))
    # A fresh window: the last failure was long enough ago to forgive.
    if now - first > WINDOW_SECONDS:
        count, first = 0, now
    count += 1
    if count >= MAX_ATTEMPTS:
        locked_until = now + LOCKOUT_SECONDS
    _failures[key] = (count, first, locked_until)


def record_success(identity: str) -> None:
    """A correct password clears the account's history."""
    _failures.pop(_key(identity), None)


def reset() -> None:
    """Drop every counter (tests)."""
    _failures.clear()
