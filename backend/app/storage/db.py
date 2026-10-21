import sqlite3
from contextlib import contextmanager
from pathlib import Path

# DB 파일은 backend/data/slot-flow.db 다. Git에는 넣지 않는다. (D-034)
DEFAULT_DB_PATH = Path(__file__).resolve().parents[2] / "data" / "slot-flow.db"

_db_path = DEFAULT_DB_PATH

SCHEMA = [
    """
    CREATE TABLE IF NOT EXISTS resources (
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
    CREATE TABLE IF NOT EXISTS operating_hours (
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
    CREATE TABLE IF NOT EXISTS reservations (
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
    CREATE INDEX IF NOT EXISTS reservations_resource_start
        ON reservations (resource_id, start_at)
    """,
    # 겹침의 최종 보장. 부등호가 엄격해 끝과 시작이 맞닿으면 겹침이 아니다. (D-003, D-009, D-032)
    # 변경 시 트리거는 상태를 바꾸는 취소(R-008)와 함께 둔다.
    """
    CREATE TRIGGER IF NOT EXISTS reservations_no_overlap_insert
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


def set_db_path(path: Path) -> None:
    global _db_path
    _db_path = Path(path)


def connect() -> sqlite3.Connection:
    # isolation_level=None: 쓰기 단위는 BEGIN IMMEDIATE로 직접 시작한다. (D-032, D-035)
    conn = sqlite3.connect(_db_path, timeout=5, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db() -> None:
    _db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = connect()
    try:
        for statement in SCHEMA:
            conn.execute(statement)
    finally:
        conn.close()


@contextmanager
def write_unit(conn: sqlite3.Connection):
    """쓰기 단위. 저장소를 읽는 첫 판정 전에 시작하고, 거부·실패하면 전부 되돌린다. (D-035)"""
    conn.execute("BEGIN IMMEDIATE")
    try:
        yield
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    conn.execute("COMMIT")
