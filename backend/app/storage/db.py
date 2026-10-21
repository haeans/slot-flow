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
