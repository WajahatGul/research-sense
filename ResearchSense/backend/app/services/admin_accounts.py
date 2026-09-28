"""Named administrator accounts, and a record of what each one did.

There used to be one shared admin login, read from .env on every sign-in.
Nobody could tell who approved a claim or removed a paper (a repudiation
gap), the password could not be changed without redeploying, and taking
access away from one person meant changing it for everyone.

Now each administrator has their own account in the database. The .env
login only seeds the first one, the first time the app starts with none;
from then on the database is the authority. A deactivated administrator's
existing session stops working at once, because every admin request checks
the account, not just the token. Every consequential action is written to
the append-only audit log.
"""

from __future__ import annotations

import os
import re

from app.core.security import hash_password, verify_password
from app.repositories.accounts import AccountStore

MIN_PASSWORD = 12
_USERNAME = re.compile(r"^[a-z0-9._-]{3,40}$")


class AdminError(ValueError):
    """A request an administrator can fix (shown to them as is)."""


def ensure_first_admin() -> None:
    """Seed the first administrator from ADMIN_USERNAME/ADMIN_PASSWORD."""
    store = AccountStore.instance()
    if store.count_admins():
        return
    password = os.getenv("ADMIN_PASSWORD", "")
    if not password:
        return
    username = os.getenv("ADMIN_USERNAME", "admin").strip().lower() or "admin"
    store.create_admin(username, hash_password(password),
                       weak=len(password) < MIN_PASSWORD, created_by="setup (.env)")
    store.record("system", "admin.created", username, "first administrator, from .env")


def authenticate(username: str, password: str) -> dict | None:
    ensure_first_admin()
    admin = AccountStore.instance().get_admin(username.strip().lower())
    if admin and admin["active"] and verify_password(password, admin["password_hash"]):
        return admin
    return None


def is_active(username: str) -> bool:
    ensure_first_admin()
    admin = AccountStore.instance().get_admin(username)
    return bool(admin and admin["active"])


def _check_password(password: str) -> None:
    if len(password) < MIN_PASSWORD:
        raise AdminError(f"Use at least {MIN_PASSWORD} characters. A passphrase of a few "
                         "words is easier to remember and harder to guess.")


def add_admin(by: str, username: str, password: str) -> None:
    username = username.strip().lower()
    if not _USERNAME.match(username):
        raise AdminError("Usernames are 3 to 40 lowercase letters, digits, dots, "
                         "hyphens or underscores.")
    _check_password(password)
    store = AccountStore.instance()
    if store.get_admin(username):
        raise AdminError("That username is taken.")
    store.create_admin(username, hash_password(password), weak=False, created_by=by)
    store.record(by, "admin.created", username)


def set_active(by: str, username: str, active: bool) -> None:
    store = AccountStore.instance()
    if store.get_admin(username) is None:
        raise AdminError("No such administrator.")
    if not active:
        if username == by:
            raise AdminError("You cannot deactivate your own account.")
        others = [a for a in store.list_admins() if a["active"] and a["username"] != username]
        if not others:
            raise AdminError("At least one administrator must stay active.")
    store.set_admin_active(username, active)
    store.record(by, "admin.activated" if active else "admin.deactivated", username)


def change_password(username: str, current: str, new: str) -> None:
    store = AccountStore.instance()
    admin = store.get_admin(username)
    if admin is None or not verify_password(current, admin["password_hash"]):
        raise AdminError("The current password is not right.")
    _check_password(new)
    store.set_admin_password(username, hash_password(new))
    store.record(username, "admin.password_changed", username)
