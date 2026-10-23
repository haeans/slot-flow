import sqlite3
from contextlib import contextmanager
from pathlib import Path

from alembic import command
from alembic.config import Config

# DB 파일은 backend/data/slot-flow.db 다. Git에는 넣지 않는다. (D-034)
DEFAULT_DB_PATH = Path(__file__).resolve().parents[2] / "data" / "slot-flow.db"

# DB 구조는 alembic 절차(backend/migrations)로만 만들고 바꾼다. (D-064)
ALEMBIC_INI = Path(__file__).resolve().parents[2] / "alembic.ini"

_db_path = DEFAULT_DB_PATH


def set_db_path(path: Path) -> None:
    global _db_path
    _db_path = Path(path)


def get_db_path() -> Path:
    return _db_path


def connect() -> sqlite3.Connection:
    # isolation_level=None: 쓰기 단위는 BEGIN IMMEDIATE로 직접 시작한다. (D-032, D-035)
    conn = sqlite3.connect(_db_path, timeout=5, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db() -> None:
    """서버를 시작할 때 최신 절차까지 적용한다. 없으면 DB 파일을 새로 만든다. (D-034, D-064)"""
    _db_path.parent.mkdir(parents=True, exist_ok=True)
    config = Config(str(ALEMBIC_INI))
    config.attributes["skip_logging"] = True
    command.upgrade(config, "head")
    # journal_mode=WAL 은 DB 파일에 남는다. 절차를 적용한 뒤 한 번 연결해 켜 둔다. (D-032)
    connect().close()


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
