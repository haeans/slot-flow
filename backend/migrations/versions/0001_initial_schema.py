"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-10-22 16:56:27.874842

M1 의 구조(자원·운영시간·예약, 인덱스, 겹침 트리거)를 그대로 옮겼다. (D-029~D-033, D-064)
"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = '0001'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


UPGRADE = [
    """
    CREATE TABLE resources (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        min_duration_minutes INTEGER NOT NULL
            CHECK (min_duration_minutes > 0 AND min_duration_minutes % 30 = 0),
        max_duration_minutes INTEGER NOT NULL
            CHECK (max_duration_minutes > 0 AND max_duration_minutes % 30 = 0),
        cancel_deadline_hours INTEGER NOT NULL,
        CHECK (min_duration_minutes <= max_duration_minutes)
    ) STRICT
    """,
    # 요일마다 한 구간. 운영하지 않는 요일은 행이 없다. (D-019, D-031)
    """
    CREATE TABLE operating_hours (
        resource_id INTEGER NOT NULL REFERENCES resources(id),
        weekday TEXT NOT NULL
            CHECK (weekday IN ('mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun')),
        open_time TEXT NOT NULL
            CHECK (open_time GLOB '[0-2][0-9]:[03]0' AND substr(open_time, 1, 2) <= '23'),
        close_time TEXT NOT NULL
            CHECK (close_time GLOB '[0-2][0-9]:[03]0' AND substr(close_time, 1, 2) <= '23'),
        PRIMARY KEY (resource_id, weekday),
        CHECK (open_time < close_time)
    ) STRICT
    """,
    # 예약. id는 내부 키이고 API에 내보내지 않는다. (D-029, D-030, D-033)
    """
    CREATE TABLE reservations (
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
    """,
    """
    CREATE INDEX reservations_resource_start
        ON reservations (resource_id, start_at)
    """,
    # 겹침의 최종 보장. 부등호가 엄격해 끝과 시작이 맞닿으면 겹침이 아니다. (D-003, D-009, D-032)
    # 변경 시 트리거는 상태를 바꾸는 취소(R-008)와 함께 둔다.
    """
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
    """,
]

DOWNGRADE = [
    "DROP TRIGGER reservations_no_overlap_insert",
    "DROP INDEX reservations_resource_start",
    "DROP TABLE reservations",
    "DROP TABLE operating_hours",
    "DROP TABLE resources",
]


def upgrade() -> None:
    for statement in UPGRADE:
        op.execute(statement)


def downgrade() -> None:
    for statement in DOWNGRADE:
        op.execute(statement)
