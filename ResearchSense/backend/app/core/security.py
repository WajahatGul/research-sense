"""Password hashing and JWT session tokens.

Passwords: PBKDF2-HMAC-SHA256 (stdlib) with a per-user random salt.
Tokens: signed JWT (PyJWT), 7-day expiry. The signing secret comes from the
JWT_SECRET env var when set; otherwise a generated secret is persisted in the
accounts database so tokens survive restarts without any configuration.
"""
from __future__ import annotations

import hashlib
import os
import secrets
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.repositories.accounts import AccountStore

_ITERATIONS = 200_000
TOKEN_DAYS = 7
_bearer = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode(), bytes.fromhex(salt), _ITERATIONS).hex()
    return f"{salt}${digest}"


def verify_password(password: str, stored: str) -> bool:
    try:
        salt, digest = stored.split("$", 1)
    except ValueError:
        return False
    candidate = hashlib.pbkdf2_hmac(
        "sha256", password.encode(), bytes.fromhex(salt), _ITERATIONS).hex()
    return secrets.compare_digest(candidate, digest)


def _secret() -> str:
    env = os.getenv("JWT_SECRET")
    if env:
        return env
    return AccountStore.instance().jwt_secret()


def create_token(subject: str, role: str) -> str:
    payload = {
        "sub": subject,
        "role": role,
        "exp": datetime.now(timezone.utc) + timedelta(days=TOKEN_DAYS),
    }
    return jwt.encode(payload, _secret(), algorithm="HS256")


def _decode(credentials: HTTPAuthorizationCredentials | None) -> dict:
    if credentials is None:
        raise HTTPException(status_code=401, detail="Not signed in")
    try:
        return jwt.decode(credentials.credentials, _secret(), algorithms=["HS256"])
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Session expired or invalid")


def current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> dict:
    """FastAPI dependency: any signed-in account (researcher or admin)."""
    return _decode(credentials)


def current_admin(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> dict:
    """FastAPI dependency: admin accounts only."""
    payload = _decode(credentials)
    if payload.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return payload
