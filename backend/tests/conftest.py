import os
from datetime import datetime

import pytest

# 테스트 전용 세션 비밀값. 실제 값은 backend/.env 에만 있다. (D-049)
os.environ["SLOTFLOW_SESSION_SECRET"] = "test-only-secret-" + "0" * 64

from fastapi.testclient import TestClient

from app.main import app
from app.storage import db
from app.validation import reservation_rules

# 테스트의 "지금". 2026-11-02(월)보다 앞선 날이다.
FIXED_NOW = datetime(2026, 10, 21, 12, 0, tzinfo=reservation_rules.KST)


@pytest.fixture(autouse=True)
def fixed_now(monkeypatch):
    monkeypatch.setattr(reservation_rules, "now_seoul", lambda: FIXED_NOW)


@pytest.fixture
def client(tmp_path):
    # 테스트마다 임시 DB를 쓴다. backend/data/slot-flow.db는 건드리지 않는다.
    db.set_db_path(tmp_path / "test.db")
    with TestClient(app) as c:
        yield c
    db.set_db_path(db.DEFAULT_DB_PATH)


@pytest.fixture
def tmp_db(tmp_path):
    # 서버 없이 서비스·명령을 부를 때 쓰는 임시 DB
    db.set_db_path(tmp_path / "test.db")
    yield
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
