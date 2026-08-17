"""Porto password hashing and verification."""

from __future__ import annotations

import base64
import hashlib
import hmac
import os
import secrets
from datetime import datetime, timedelta, timezone


SCRYPT_N = 2**14
SCRYPT_R = 8
SCRYPT_P = 1
LOGIN_FAILURE_LIMIT = 5
LOGIN_LOCK_MINUTES = 15
SESSION_IDLE_MINUTES = 30
SESSION_MAX_HOURS = 8
TOKEN_TTL_MINUTES = 30


def hash_password(password: str) -> str:
    if len(password) < 8:
        raise ValueError("비밀번호는 8자 이상이어야 합니다.")
    salt = os.urandom(16)
    digest = hashlib.scrypt(
        password.encode(), salt=salt, n=SCRYPT_N, r=SCRYPT_R, p=SCRYPT_P
    )
    return "scrypt${}${}${}${}${}".format(
        SCRYPT_N,
        SCRYPT_R,
        SCRYPT_P,
        base64.urlsafe_b64encode(salt).decode(),
        base64.urlsafe_b64encode(digest).decode(),
    )


def verify_password(password: str, encoded: str | None) -> bool:
    if not encoded:
        return False
    try:
        algorithm, n, r, p, salt, expected = encoded.split("$", 5)
        if algorithm != "scrypt":
            return False
        digest = hashlib.scrypt(
            password.encode(),
            salt=base64.urlsafe_b64decode(salt),
            n=int(n), r=int(r), p=int(p),
        )
        return hmac.compare_digest(digest, base64.urlsafe_b64decode(expected))
    except (ValueError, TypeError):
        return False


def new_account_token() -> tuple[str, str, datetime]:
    """Return a one-time token, its SHA-256 digest, and a UTC expiry."""
    token = secrets.token_urlsafe(32)
    digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
    expires_at = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(
        minutes=TOKEN_TTL_MINUTES
    )
    return token, digest, expires_at


def verify_account_token(token: str, digest: str | None) -> bool:
    if not token or not digest:
        return False
    actual = hashlib.sha256(token.strip().encode("utf-8")).hexdigest()
    return hmac.compare_digest(actual, digest)
