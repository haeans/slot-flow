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


def week_hours(**days):
    """일곱 요일 키를 모두 채운다. 따로 주지 않은 요일은 운영하지 않음(null)."""
    hours = {day: None for day in ("mon", "tue", "wed", "thu", "fri", "sat", "sun")}
    hours.update(days)
    return hours


def resource_body(**overrides):
    body = {
        "name": "공방 작업대 A",
        "operating_hours": week_hours(mon={"open": "10:00", "close": "12:00"}),
        "min_duration_minutes": 30,
        "max_duration_minutes": 120,
        "cancel_deadline_hours": 24,
    }
    body.update(overrides)
    return body
