import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.storage import db


@pytest.fixture
def client(tmp_path):
    # 테스트마다 임시 DB를 쓴다. backend/data/slot-flow.db는 건드리지 않는다.
    db.set_db_path(tmp_path / "test.db")
    with TestClient(app) as c:
        yield c
    db.set_db_path(db.DEFAULT_DB_PATH)


def resource_body(**overrides):
    body = {
        "name": "공방 작업대 A",
        "min_duration_minutes": 30,
        "max_duration_minutes": 120,
        "cancel_deadline_hours": 24,
    }
    body.update(overrides)
    return body
