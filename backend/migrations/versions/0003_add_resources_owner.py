"""add resources owner

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-22 18:00:00

자원마다 소유 운영자(owner_account_id, 필수)를 둔다. (D-044, D-057, DATA-MIGRATION-PLAN 3.1)
기본값 없는 NOT NULL 외래키는 ALTER 로 더할 수 없어 테이블을 새로 만들어 바꿔 끼운다.
소유자를 정할 수 없는 자원이 있으면 멈춘다. 절차는 데이터를 지우지 않는다. (D-064)
"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = '0003'
down_revision: Union[str, Sequence[str], None] = '0002'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


COLUMNS = """
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        min_duration_minutes INTEGER NOT NULL
            CHECK (min_duration_minutes > 0 AND min_duration_minutes % 30 = 0),
        max_duration_minutes INTEGER NOT NULL
            CHECK (max_duration_minutes > 0 AND max_duration_minutes % 30 = 0),
        cancel_deadline_hours INTEGER NOT NULL,"""

COPY = "id, name, min_duration_minutes, max_duration_minutes, cancel_deadline_hours"


def _swap(create_sql: str, copy_columns: str) -> None:
    # operating_hours·reservations 가 resources 를 가리키므로, 바꿔 끼우는 동안의 외래키 검사는 끝까지 미룬다.
    op.execute("PRAGMA defer_foreign_keys = ON")
    op.execute(create_sql)
    op.execute(f"INSERT INTO resources_new ({copy_columns}) SELECT {copy_columns} FROM resources")
    op.execute("DROP TABLE resources")
    op.execute("ALTER TABLE resources_new RENAME TO resources")


def upgrade() -> None:
    count = op.get_bind().exec_driver_sql("SELECT count(*) FROM resources").scalar()
    if count:
        raise RuntimeError(
            f"소유 운영자가 없는 자원이 있습니다({count}개). "
            "개발용 자원이면 resources·operating_hours·reservations 를 정리한 뒤 다시 적용하세요. (D-064)"
        )
    _swap(
        f"""
        CREATE TABLE resources_new ({COLUMNS}
            owner_account_id INTEGER NOT NULL REFERENCES accounts(id),
            CHECK (min_duration_minutes <= max_duration_minutes)
        ) STRICT
        """,
        COPY,
    )
    op.execute("CREATE INDEX resources_owner ON resources (owner_account_id)")


def downgrade() -> None:
    op.execute("DROP INDEX resources_owner")
    _swap(
        f"""
        CREATE TABLE resources_new ({COLUMNS}
            CHECK (min_duration_minutes <= max_duration_minutes)
        ) STRICT
        """,
        COPY,
    )
