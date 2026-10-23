import pytest

from app.create_admin import create_admin
from app.errors import ApiError
from app.reset_password import reset_password
from app.services import accounts
from app.storage import db

# 관리자 계정 생성·비밀번호 재설정 명령 (D-050, D-059)


def load(email):
    conn = db.connect()
    try:
        return accounts.find_by_email(conn, email)
    finally:
        conn.close()


def test_create_admin(tmp_db):
    account = create_admin("  Admin@Example.com ", " 관리자 ", "admin-pass-1")
    assert account == {
        "email": "admin@example.com", "name": "관리자", "role": "admin",
        "operator_status": None, "booking_slug": None,
    }
    row = load("admin@example.com")
    assert row["password_hash"].startswith("$argon2id$")
    assert accounts.PASSWORDS.verify("admin-pass-1", row["password_hash"])


def test_second_admin_is_refused(tmp_db):
    create_admin("admin@example.com", "관리자", "admin-pass-1")
    with pytest.raises(ApiError) as exc:
        create_admin("other@example.com", "관리자2", "admin-pass-2")
    assert exc.value.code == "ADMIN_EXISTS"


@pytest.mark.parametrize(
    "email, name, password",
    [("no-at-sign", "관리자", "admin-pass-1"), ("a@example.com", "", "admin-pass-1"),
     ("a@example.com", "관리자", "short")],
)
def test_create_admin_rejects_invalid_input(tmp_db, email, name, password):
    with pytest.raises(ApiError) as exc:
        create_admin(email, name, password)
    assert exc.value.code == "INVALID_INPUT"


def test_reset_password_clears_sessions_and_failures(tmp_db):
    create_admin("admin@example.com", "관리자", "admin-pass-1")
    conn = db.connect()
    account_id = load("admin@example.com")["id"]
    conn.execute(
        "INSERT INTO sessions VALUES (?, ?, ?, ?)",
        ("a" * 64, account_id, "2026-10-21T12:00:00+09:00", "2026-10-28T12:00:00+09:00"),
    )
    conn.execute(
        "INSERT INTO login_failures VALUES ('admin@example.com', 2, '2026-10-21T12:00:00+09:00', NULL)"
    )
    conn.close()

    assert reset_password("ADMIN@example.com", "new-pass-123") is True
    row = load("admin@example.com")
    assert accounts.PASSWORDS.verify("new-pass-123", row["password_hash"])
    conn = db.connect()
    assert conn.execute("SELECT count(*) FROM sessions").fetchone()[0] == 0
    assert conn.execute("SELECT count(*) FROM login_failures").fetchone()[0] == 0
    conn.close()


def test_reset_password_unknown_email(tmp_db):
    assert reset_password("nobody@example.com", "new-pass-123") is False
