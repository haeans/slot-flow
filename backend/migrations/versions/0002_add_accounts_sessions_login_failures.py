"""add accounts sessions login_failures

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-22 16:56:27.874842

계정·세션·로그인 실패 기록을 더한다. 기존 테이블은 바꾸지 않는다.
자원의 소유 운영자(0003)와 예약의 회원 계정(0004)은 그 기능을 만드는 단계에서 더한다.
(DATA-MIGRATION-PLAN 2절, D-049, D-056, D-059, D-062, D-063)
"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = '0002'
down_revision: Union[str, Sequence[str], None] = '0001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# 계정·세션의 시각. 예약 시각과 같은 형식이지만 초까지 쓴다. (DATA-MIGRATION-PLAN 4절)
TS = "'[0-9][0-9][0-9][0-9]-[0-1][0-9]-[0-3][0-9]T[0-2][0-9]:[0-5][0-9]:[0-5][0-9]+09:00'"

UPGRADE = [
    f"""
    CREATE TABLE accounts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT NOT NULL UNIQUE
            CHECK (email = lower(email) AND length(email) BETWEEN 3 AND 254 AND instr(email, '@') > 1),
        password_hash TEXT NOT NULL CHECK (password_hash GLOB '$argon2id$*'),
        name TEXT NOT NULL CHECK (name = trim(name) AND length(name) BETWEEN 1 AND 50),
        role TEXT NOT NULL CHECK (role IN ('admin', 'operator', 'customer')),
        operator_status TEXT CHECK (operator_status IN ('pending', 'approved', 'suspended')),
        booking_slug TEXT UNIQUE
            CHECK (length(booking_slug) BETWEEN 3 AND 30
                   AND booking_slug NOT GLOB '*[^a-z0-9-]*'
                   AND booking_slug NOT GLOB '-*'
                   AND booking_slug NOT GLOB '*-'),
        created_at TEXT NOT NULL CHECK (created_at GLOB {TS}),
        CHECK ((role = 'operator') = (operator_status IS NOT NULL)),
        CHECK ((role = 'operator') = (booking_slug IS NOT NULL))
    ) STRICT
    """,
    # 관리자는 1명이다. (D-050)
    """
    CREATE UNIQUE INDEX accounts_single_admin ON accounts (role) WHERE role = 'admin'
    """,
    # 토큰 원문이 아니라 HMAC-SHA256 값만 둔다. (D-049)
    f"""
    CREATE TABLE sessions (
        token_hash TEXT PRIMARY KEY
            CHECK (length(token_hash) = 64 AND token_hash NOT GLOB '*[^0-9a-f]*'),
        account_id INTEGER NOT NULL REFERENCES accounts(id),
        created_at TEXT NOT NULL CHECK (created_at GLOB {TS}),
        expires_at TEXT NOT NULL CHECK (expires_at GLOB {TS}),
        CHECK (created_at < expires_at)
    ) STRICT
    """,
    # 정지할 때 그 운영자의 세션을 한꺼번에 지운다. (D-053)
    """
    CREATE INDEX sessions_account ON sessions (account_id)
    """,
    # 계정이 없는 이메일도 똑같이 기록하므로 accounts 를 가리키지 않는다. (D-054, D-062)
    f"""
    CREATE TABLE login_failures (
        email TEXT PRIMARY KEY CHECK (email = lower(email)),
        failed_count INTEGER NOT NULL CHECK (failed_count BETWEEN 1 AND 5),
        last_failed_at TEXT NOT NULL CHECK (last_failed_at GLOB {TS}),
        locked_until TEXT CHECK (locked_until GLOB {TS}),
        CHECK ((failed_count = 5) = (locked_until IS NOT NULL))
    ) STRICT
    """,
]

DOWNGRADE = [
    "DROP TABLE login_failures",
    "DROP INDEX sessions_account",
    "DROP TABLE sessions",
    "DROP INDEX accounts_single_admin",
    "DROP TABLE accounts",
]


def upgrade() -> None:
    for statement in UPGRADE:
        op.execute(statement)


def downgrade() -> None:
    for statement in DOWNGRADE:
        op.execute(statement)
