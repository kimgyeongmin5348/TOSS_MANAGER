"""Security-sensitive account persistence and lifecycle operations."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import Engine, text

from .auth import (
    LOGIN_FAILURE_LIMIT,
    LOGIN_LOCK_MINUTES,
    hash_password,
    new_account_token,
    verify_account_token,
    verify_password,
)


@dataclass(frozen=True)
class LoginResult:
    status: str
    user: dict[str, Any] | None = None
    locked_until: datetime | None = None


def authenticate_with_limit(engine: Engine, email: str, password: str) -> LoginResult:
    normalized = email.strip().lower()
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    with engine.begin() as connection:
        row = connection.execute(text("""
            SELECT user_id, email, display_name, password_hash, failed_login_count,
                   locked_until, session_version, email_verified
            FROM app_users WHERE email=:email
        """), {"email": normalized}).mappings().first()
        if not row:
            # Preserve the same public response for unknown emails.
            return LoginResult("invalid")
        if row["locked_until"] and row["locked_until"] > now:
            return LoginResult("locked", locked_until=row["locked_until"])
        if not verify_password(password, row["password_hash"]):
            failures = int(row["failed_login_count"] or 0) + 1
            locked_until = None
            if failures >= LOGIN_FAILURE_LIMIT:
                locked_until = now + timedelta(minutes=LOGIN_LOCK_MINUTES)
                failures = 0
            connection.execute(text("""
                UPDATE app_users SET failed_login_count=:failures,
                  locked_until=:locked_until WHERE user_id=:user_id
            """), {
                "failures": failures, "locked_until": locked_until,
                "user_id": row["user_id"],
            })
            return LoginResult("locked" if locked_until else "invalid", locked_until=locked_until)
        connection.execute(text("""
            UPDATE app_users SET failed_login_count=0, locked_until=NULL,
              last_login_at=:now WHERE user_id=:user_id
        """), {"now": now, "user_id": row["user_id"]})
    return LoginResult("success", user={
        "user_id": int(row["user_id"]), "email": row["email"],
        "display_name": row["display_name"],
        "session_version": int(row["session_version"] or 1),
        "email_verified": bool(row["email_verified"]),
    })


def change_password(
    engine: Engine, *, user_id: int, current_password: str, new_password: str
) -> int:
    new_hash = hash_password(new_password)
    with engine.begin() as connection:
        row = connection.execute(text("""
            SELECT password_hash, session_version FROM app_users WHERE user_id=:user_id
        """), {"user_id": user_id}).mappings().one()
        if not verify_password(current_password, row["password_hash"]):
            raise ValueError("현재 비밀번호가 올바르지 않습니다.")
        version = int(row["session_version"] or 1) + 1
        connection.execute(text("""
            UPDATE app_users SET password_hash=:password_hash,
              session_version=:version, password_reset_token_hash=NULL,
              password_reset_expires_at=NULL WHERE user_id=:user_id
        """), {"password_hash": new_hash, "version": version, "user_id": user_id})
    return version


def create_email_verification(engine: Engine, *, user_id: int) -> tuple[str, str]:
    token, digest, expires = new_account_token()
    with engine.begin() as connection:
        email = connection.execute(text(
            "SELECT email FROM app_users WHERE user_id=:user_id"
        ), {"user_id": user_id}).scalar_one()
        connection.execute(text("""
            UPDATE app_users SET email_verification_token_hash=:digest,
              email_verification_expires_at=:expires WHERE user_id=:user_id
        """), {"digest": digest, "expires": expires, "user_id": user_id})
    return str(email), token


def confirm_email_verification(engine: Engine, *, user_id: int, token: str) -> bool:
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    with engine.begin() as connection:
        row = connection.execute(text("""
            SELECT email_verification_token_hash AS digest,
                   email_verification_expires_at AS expires
            FROM app_users WHERE user_id=:user_id
        """), {"user_id": user_id}).mappings().one()
        if not row["expires"] or row["expires"] < now or not verify_account_token(token, row["digest"]):
            return False
        connection.execute(text("""
            UPDATE app_users SET email_verified=TRUE, email_verified_at=:verified_at,
              email_verification_token_hash=NULL, email_verification_expires_at=NULL
            WHERE user_id=:user_id
        """), {"user_id": user_id, "verified_at": now})
    return True


def create_password_reset(engine: Engine, *, email: str) -> tuple[int, str, str] | None:
    token, digest, expires = new_account_token()
    with engine.begin() as connection:
        row = connection.execute(text(
            "SELECT user_id, email FROM app_users WHERE email=:email"
        ), {"email": email.strip().lower()}).mappings().first()
        if not row:
            return None
        connection.execute(text("""
            UPDATE app_users SET password_reset_token_hash=:digest,
              password_reset_expires_at=:expires WHERE user_id=:user_id
        """), {"digest": digest, "expires": expires, "user_id": row["user_id"]})
    return int(row["user_id"]), str(row["email"]), token


def reset_password(engine: Engine, *, email: str, token: str, password: str) -> bool:
    new_hash = hash_password(password)
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    with engine.begin() as connection:
        row = connection.execute(text("""
            SELECT user_id, password_reset_token_hash AS digest,
                   password_reset_expires_at AS expires, session_version
            FROM app_users WHERE email=:email
        """), {"email": email.strip().lower()}).mappings().first()
        if not row or not row["expires"] or row["expires"] < now:
            return False
        if not verify_account_token(token, row["digest"]):
            return False
        connection.execute(text("""
            UPDATE app_users SET password_hash=:password_hash,
              session_version=:version, failed_login_count=0, locked_until=NULL,
              password_reset_token_hash=NULL, password_reset_expires_at=NULL
            WHERE user_id=:user_id
        """), {
            "password_hash": new_hash, "version": int(row["session_version"] or 1) + 1,
            "user_id": row["user_id"],
        })
    return True


def list_linked_accounts(engine: Engine, *, user_id: int) -> list[dict[str, Any]]:
    with engine.connect() as connection:
        return list(connection.execute(text("""
            SELECT account_id, account_no_masked, account_type, provider,
                   is_active, updated_at FROM brokerage_accounts
            WHERE user_id=:user_id ORDER BY created_at
        """), {"user_id": user_id}).mappings())


def current_session_version(engine: Engine, *, user_id: int) -> int | None:
    with engine.connect() as connection:
        value = connection.execute(text(
            "SELECT session_version FROM app_users WHERE user_id=:user_id"
        ), {"user_id": user_id}).scalar()
    return int(value) if value is not None else None


def disconnect_account(engine: Engine, *, user_id: int, account_id: int) -> None:
    with engine.begin() as connection:
        result = connection.execute(text("""
            UPDATE brokerage_accounts SET is_active=FALSE
            WHERE user_id=:user_id AND account_id=:account_id
        """), {"user_id": user_id, "account_id": account_id})
        if result.rowcount != 1:
            raise ValueError("연결된 계좌를 찾지 못했습니다.")


def delete_user_data(engine: Engine, *, user_id: int, password: str) -> None:
    """Delete private user/account data; shared market data remains anonymized."""
    with engine.begin() as connection:
        encoded = connection.execute(text(
            "SELECT password_hash FROM app_users WHERE user_id=:user_id"
        ), {"user_id": user_id}).scalar_one()
        if not verify_password(password, encoded):
            raise ValueError("비밀번호가 올바르지 않습니다.")
        connection.execute(text("DELETE FROM watchlist_items WHERE user_id=:user_id"), {"user_id": user_id})
        connection.execute(text("""
            DELETE FROM holding_snapshot_items WHERE snapshot_id IN (
              SELECT ps.snapshot_id FROM portfolio_snapshots ps
              JOIN brokerage_accounts ba ON ba.account_id=ps.account_id
              WHERE ba.user_id=:user_id)
        """), {"user_id": user_id})
        connection.execute(text("""
            DELETE FROM portfolio_snapshots WHERE account_id IN (
              SELECT account_id FROM brokerage_accounts WHERE user_id=:user_id)
        """), {"user_id": user_id})
        connection.execute(text("DELETE FROM brokerage_accounts WHERE user_id=:user_id"), {"user_id": user_id})
        connection.execute(text("DELETE FROM app_users WHERE user_id=:user_id"), {"user_id": user_id})
