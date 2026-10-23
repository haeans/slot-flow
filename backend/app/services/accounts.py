import sqlite3

from pwdlib import PasswordHash

from app.errors import ApiError
from app.storage.db import write_unit
from app.validation import reservation_rules as rules

# 비밀번호 계산·검증은 여기 한 곳에서 한다. argon2id, 라이브러리 기본 설정. (D-007, D-063)
PASSWORDS = PasswordHash.recommended()


def hash_password(password: str) -> str:
    return PASSWORDS.hash(password)


def now_text() -> str:
    """계정·세션의 시각. 초까지 쓴다. (DATA-MIGRATION-PLAN 4절)"""
    return rules.now_seoul().replace(microsecond=0).isoformat()


def account_object(row: sqlite3.Row) -> dict:
    # 내부 키, 비밀번호 값은 응답에 담지 않는다. (API-SPEC-CHANGE 1.4)
    return {
        "email": row["email"],
        "name": row["name"],
        "role": row["role"],
        "operator_status": row["operator_status"],
        "booking_slug": row["booking_slug"],
    }


def find_by_email(conn: sqlite3.Connection, email: str) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM accounts WHERE email = ?", (email,)).fetchone()


def admin_exists(conn: sqlite3.Connection) -> bool:
    return conn.execute("SELECT 1 FROM accounts WHERE role = 'admin'").fetchone() is not None


def create_account(conn: sqlite3.Connection, *, email: str, password_hash: str, name: str,
                   role: str, booking_slug: str | None = None) -> dict:
    """비밀번호 값은 쓰기 단위 밖에서 미리 계산해 받는다. 계산이 느리기 때문이다. (API-SPEC-CHANGE 2.1)"""
    with write_unit(conn):
        if find_by_email(conn, email) is not None:
            raise ApiError(409, "EMAIL_TAKEN", "이미 가입된 이메일입니다.")
        if booking_slug is not None and conn.execute(
            "SELECT 1 FROM accounts WHERE booking_slug = ?", (booking_slug,)
        ).fetchone():
            raise ApiError(409, "BOOKING_SLUG_TAKEN", "이미 쓰고 있는 예약 주소명입니다.")
        # 운영자는 승인 대기로 시작한다. (D-043)
        operator_status = "pending" if role == "operator" else None
        conn.execute(
            "INSERT INTO accounts (email, password_hash, name, role, operator_status,"
            " booking_slug, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (email, password_hash, name, role, operator_status, booking_slug, now_text()),
        )
        return account_object(find_by_email(conn, email))


def set_password(conn: sqlite3.Connection, email: str, password_hash: str) -> bool:
    """비밀번호를 바꾸고 그 계정의 세션과 로그인 실패 기록을 지운다. (D-059)"""
    with write_unit(conn):
        row = find_by_email(conn, email)
        if row is None:
            return False
        conn.execute("UPDATE accounts SET password_hash = ? WHERE id = ?", (password_hash, row["id"]))
        conn.execute("DELETE FROM sessions WHERE account_id = ?", (row["id"],))
        conn.execute("DELETE FROM login_failures WHERE email = ?", (email,))
        return True


def list_operators(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM accounts WHERE role = 'operator' ORDER BY created_at, id"
    ).fetchall()
    return [account_object(row) for row in rows]


# 상태를 바꿀 수 있는 이전 상태. 정지된 운영자를 다시 승인하는 기능은 PRD에 없다. (D-067)
_ALLOWED_FROM = {"approved": ("pending", "approved"), "suspended": ("pending", "approved", "suspended")}


def set_operator_status(conn: sqlite3.Connection, booking_slug: str, status: str) -> dict:
    """운영자 승인·정지. 정지하면 그 운영자의 세션을 모두 지운다. (D-043, D-053, D-067)"""
    with write_unit(conn):
        row = conn.execute(
            "SELECT * FROM accounts WHERE booking_slug = ? AND role = 'operator'", (booking_slug,)
        ).fetchone()
        if row is None:
            raise ApiError(404, "OPERATOR_NOT_FOUND", "그 예약 주소명의 운영자가 없습니다.")
        if row["operator_status"] not in _ALLOWED_FROM[status]:
            raise ApiError(409, "INVALID_OPERATOR_STATE", "정지된 운영자는 다시 승인할 수 없습니다.")
        conn.execute("UPDATE accounts SET operator_status = ? WHERE id = ?", (status, row["id"]))
        if status == "suspended":
            conn.execute("DELETE FROM sessions WHERE account_id = ?", (row["id"],))
        return account_object(
            conn.execute("SELECT * FROM accounts WHERE id = ?", (row["id"],)).fetchone()
        )
