"""add reservations customer account

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-23 10:00:00

회원 예약이면 그 회원의 계정을, 비회원 예약이면 NULL 을 둔다. (D-045, D-057, DATA-MIGRATION-PLAN 3.2)
NULL 을 허용하므로 ALTER TABLE ADD COLUMN 으로 더한다. 겹침 트리거는 이 컬럼을 보지 않는다.
"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = '0004'
down_revision: Union[str, Sequence[str], None] = '0003'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE reservations ADD COLUMN customer_account_id INTEGER REFERENCES accounts(id)")
    op.execute("CREATE INDEX reservations_customer ON reservations (customer_account_id)")


# 외래키가 걸린 컬럼은 DROP COLUMN 이 안 되어, 0001 의 구조로 테이블을 새로 만들어 바꿔 끼운다.
_OLD_TABLE = """
    CREATE TABLE reservations_new (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        reservation_code TEXT NOT NULL UNIQUE
            CHECK (length(reservation_code) = 10
                   AND reservation_code NOT GLOB '*[^23456789ABCDEFGHJKMNPQRSTUVWXYZ]*'),
        resource_id INTEGER NOT NULL REFERENCES resources(id),
        start_at TEXT NOT NULL
            CHECK (start_at GLOB '[0-9][0-9][0-9][0-9]-[0-1][0-9]-[0-3][0-9]T[0-2][0-9]:[03]0:00+09:00'),
        end_at TEXT NOT NULL
            CHECK (end_at GLOB '[0-9][0-9][0-9][0-9]-[0-1][0-9]-[0-3][0-9]T[0-2][0-9]:[03]0:00+09:00'),
        status TEXT NOT NULL DEFAULT 'reserved' CHECK (status IN ('reserved', 'cancelled')),
        customer_name TEXT NOT NULL,
        CHECK (start_at < end_at)
    ) STRICT
"""

_TRIGGER = """
    CREATE TRIGGER reservations_no_overlap_insert
    BEFORE INSERT ON reservations
    WHEN NEW.status = 'reserved'
    BEGIN
        SELECT RAISE(ABORT, 'OVERLAP')
        WHERE EXISTS (
            SELECT 1 FROM reservations
            WHERE resource_id = NEW.resource_id
              AND status = 'reserved'
              AND start_at < NEW.end_at
              AND NEW.start_at < end_at
        );
    END
"""

_COPY = "id, reservation_code, resource_id, start_at, end_at, status, customer_name"


def downgrade() -> None:
    op.execute("PRAGMA defer_foreign_keys = ON")
    op.execute(_OLD_TABLE)
    op.execute(f"INSERT INTO reservations_new ({_COPY}) SELECT {_COPY} FROM reservations")
    op.execute("DROP TABLE reservations")
    op.execute("ALTER TABLE reservations_new RENAME TO reservations")
    op.execute("CREATE INDEX reservations_resource_start ON reservations (resource_id, start_at)")
    op.execute(_TRIGGER)
