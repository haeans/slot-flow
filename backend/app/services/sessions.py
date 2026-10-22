import hashlib
import hmac
import secrets
import sqlite3
from datetime import datetime, timedelta

from app import config
from app.errors import ApiError
from app.services import accounts
from app.storage.db import write_unit
from app.validation import reservation_rules as rules

COOKIE_NAME = "slotflow_session"
SESSION_DAYS = 7
# 같은 이메일로 5번 연속 실패하면 10분 잠근다. (D-062)
MAX_FAILURES = 5
LOCK_MINUTES = 10
# 계정이 없을 때도 검증을 한 번 해서 응답 시간으로 계정 여부를 알 수 없게 한다. (D-054)
_DUMMY_HASH = accounts.hash_password("dummy-password-for-timing")


def unauthenticated(message: str = "로그인이 필요합니다.") -> ApiError:
    return ApiError(401, "UNAUTHENTICATED", message)


def _now() -> datetime:
    return rules.now_seoul().replace(microsecond=0)


def token_hash(token: str) -> str:
    """DB 에는 토큰 원문이 아니라 HMAC-SHA256 값만 둔다. (D-049)"""
    return hmac.new(config.session_secret(), token.encode(), hashlib.sha256).hexdigest()


def _record_failure(conn: sqlite3.Connection, email: str) -> None:
    now = _now()
    with write_unit(conn):
        # 하루보다 오래됐고 잠기지 않은 기록은 지운다. (DATA-MIGRATION-PLAN 2.3)
        conn.execute(
            "DELETE FROM login_failures WHERE last_failed_at < ?"
            " AND (locked_until IS NULL OR locked_until <= ?)",
            ((now - timedelta(days=1)).isoformat(), now.isoformat()),
        )
        row = conn.execute("SELECT * FROM login_failures WHERE email = ?", (email,)).fetchone()
        if row is None or (row["locked_until"] is not None and row["locked_until"] <= now.isoformat()):
            # 잠금이 풀린 뒤의 실패는 1번부터 다시 센다.
            count = 1
        else:
            count = min(row["failed_count"] + 1, MAX_FAILURES)
        locked_until = (now + timedelta(minutes=LOCK_MINUTES)).isoformat() if count == MAX_FAILURES else None
        if row is not None and row["locked_until"] is not None and count == MAX_FAILURES:
            locked_until = row["locked_until"]
        conn.execute(
            "INSERT INTO login_failures (email, failed_count, last_failed_at, locked_until)"
            " VALUES (?, ?, ?, ?) ON CONFLICT (email) DO UPDATE SET"
            " failed_count = excluded.failed_count, last_failed_at = excluded.last_failed_at,"
            " locked_until = excluded.locked_until",
            (email, count, now.isoformat(), locked_until),
        )


def login(conn: sqlite3.Connection, email: str, password: str) -> tuple[dict, str]:
    """판정 순서는 API-SPEC-CHANGE 2.2 를 따른다. 성공하면 (계정 객체, 토큰 원문)을 돌려준다."""
    now = _now()
    failure = conn.execute(
        "SELECT locked_until FROM login_failures WHERE email = ?", (email,)
    ).fetchone()
    if failure is not None and failure["locked_until"] is not None and failure["locked_until"] > now.isoformat():
        raise ApiError(429, "TOO_MANY_ATTEMPTS", "로그인 시도가 너무 많습니다. 10분 뒤에 다시 시도해 주세요.")

    row = accounts.find_by_email(conn, email)
    valid, new_hash = accounts.PASSWORDS.verify_and_update(
        password, row["password_hash"] if row is not None else _DUMMY_HASH
    )
    if row is None or not valid:
        _record_failure(conn, email)
        raise unauthenticated("이메일 또는 비밀번호가 올바르지 않습니다.")

    # 정지 여부는 비밀번호가 맞은 뒤에만 알린다. (D-053)
    if row["operator_status"] == "suspended":
        raise ApiError(403, "OPERATOR_SUSPENDED", "정지된 운영자 계정입니다. 관리자에게 문의해 주세요.")

    token = secrets.token_urlsafe(32)
    with write_unit(conn):
        conn.execute("DELETE FROM login_failures WHERE email = ?", (email,))
        if new_hash is not None:
            conn.execute("UPDATE accounts SET password_hash = ? WHERE id = ?", (new_hash, row["id"]))
        conn.execute(
            "INSERT INTO sessions (token_hash, account_id, created_at, expires_at) VALUES (?, ?, ?, ?)",
            (token_hash(token), row["id"], now.isoformat(),
             (now + timedelta(days=SESSION_DAYS)).isoformat()),
        )
    return accounts.account_object(row), token


def find_account(conn: sqlite3.Connection, token: str | None) -> sqlite3.Row | None:
    """세션 확인 (API-SPEC-CHANGE 1.6). 없거나 만료면 None. 만료된 행은 지운다."""
    if not token:
        return None
    digest = token_hash(token)
    session = conn.execute("SELECT * FROM sessions WHERE token_hash = ?", (digest,)).fetchone()
    if session is None:
        return None
    if session["expires_at"] <= _now().isoformat():
        with write_unit(conn):
            conn.execute("DELETE FROM sessions WHERE token_hash = ?", (digest,))
        return None
    return conn.execute("SELECT * FROM accounts WHERE id = ?", (session["account_id"],)).fetchone()


def logout(conn: sqlite3.Connection, token: str | None) -> None:
    if not token:
        return
    with write_unit(conn):
        conn.execute("DELETE FROM sessions WHERE token_hash = ?", (token_hash(token),))
