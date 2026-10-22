import sqlite3

import pytest
from alembic import command
from alembic.config import Config
from pwdlib import PasswordHash

from app.storage import db

# 절차 0001·0002 의 저장소 검사. (DATA-MIGRATION-PLAN 5.4)
NOW = "2026-10-21T12:00:00+09:00"
LATER = "2026-10-28T12:00:00+09:00"
HASH = PasswordHash.recommended().hash("password-1234")
TABLES = {"resources", "operating_hours", "reservations", "accounts", "sessions", "login_failures"}


@pytest.fixture
def conn(tmp_path):
    db.set_db_path(tmp_path / "test.db")
    db.init_db()
    c = db.connect()
    yield c
    c.close()
    db.set_db_path(db.DEFAULT_DB_PATH)


def add_account(conn, email="a@example.com", role="customer", status=None, slug=None, password_hash=HASH):
    return conn.execute(
        "INSERT INTO accounts (email, password_hash, name, role, operator_status, booking_slug, created_at)"
        " VALUES (?, ?, '이름', ?, ?, ?, ?)",
        (email, password_hash, role, status, slug, NOW),
    ).lastrowid


def user_tables(conn):
    rows = conn.execute("SELECT name, strict FROM pragma_table_list WHERE schema = 'main'").fetchall()
    return {r["name"]: r["strict"] for r in rows if not r["name"].startswith(("sqlite_", "alembic_"))}


def test_head_has_six_strict_tables(conn):
    tables = user_tables(conn)
    assert set(tables) == TABLES
    assert all(tables.values())
    assert conn.execute("SELECT version_num FROM alembic_version").fetchone()[0] == "0002"


def test_downgrade_to_base_and_upgrade_again(conn, tmp_path):
    config = Config(str(db.ALEMBIC_INI))
    config.attributes["skip_logging"] = True
    command.downgrade(config, "base")
    assert user_tables(conn) == {}
    command.upgrade(config, "head")
    assert set(user_tables(conn)) == TABLES


def test_pwdlib_hash_is_argon2id(conn):
    assert HASH.startswith("$argon2id$")
    add_account(conn)


def test_second_admin_rejected(conn):
    add_account(conn, "admin@example.com", role="admin")
    with pytest.raises(sqlite3.IntegrityError):
        add_account(conn, "admin2@example.com", role="admin")


@pytest.mark.parametrize(
    "kwargs",
    [
        {"email": "Upper@example.com"},
        {"email": "no-at-sign"},
        {"password_hash": "plain-text"},
        {"role": "customer", "status": "pending"},
        {"role": "operator", "status": "pending", "slug": None},
        {"role": "operator", "status": None, "slug": "kim-studio"},
        {"role": "customer", "slug": "kim-studio"},
        {"role": "operator", "status": "pending", "slug": "Kim-Studio"},
        {"role": "operator", "status": "pending", "slug": "kim_studio"},
        {"role": "operator", "status": "pending", "slug": "-kim"},
        {"role": "operator", "status": "pending", "slug": "ab"},
    ],
)
def test_invalid_account_rejected(conn, kwargs):
    with pytest.raises(sqlite3.IntegrityError):
        add_account(conn, **kwargs)


def test_duplicate_email_and_slug_rejected(conn):
    add_account(conn, "op@example.com", role="operator", status="pending", slug="kim-studio")
    with pytest.raises(sqlite3.IntegrityError):
        add_account(conn, "op@example.com")
    with pytest.raises(sqlite3.IntegrityError):
        add_account(conn, "op2@example.com", role="operator", status="pending", slug="kim-studio")


def test_session_requires_existing_account_and_hex_hash(conn):
    account_id = add_account(conn)
    token_hash = "a" * 64
    conn.execute("INSERT INTO sessions VALUES (?, ?, ?, ?)", (token_hash, account_id, NOW, LATER))
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO sessions VALUES (?, ?, ?, ?)", ("b" * 64, 999, NOW, LATER))
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO sessions VALUES (?, ?, ?, ?)", ("Z" * 64, account_id, NOW, LATER))


@pytest.mark.parametrize(
    "count, locked_until, ok",
    [(1, None, True), (5, LATER, True), (6, LATER, False), (5, None, False), (3, LATER, False)],
)
def test_login_failures_rules(conn, count, locked_until, ok):
    insert = lambda: conn.execute(
        "INSERT INTO login_failures VALUES ('x@example.com', ?, ?, ?)", (count, NOW, locked_until)
    )
    if ok:
        insert()
    else:
        with pytest.raises(sqlite3.IntegrityError):
            insert()
