import secrets
import sqlite3
from datetime import datetime

from app.errors import ApiError, resource_not_found
from app.services.resources import load_operating_hours
from app.storage.db import write_unit
from app.validation import reservation_rules as rules
from app.validation.resource_input import WEEKDAYS

# 헷갈리는 0 O 1 I L을 뺀 31자 (D-033)
CODE_ALPHABET = "23456789ABCDEFGHJKMNPQRSTUVWXYZ"
CODE_LENGTH = 10


def new_reservation_code() -> str:
    return "".join(secrets.choice(CODE_ALPHABET) for _ in range(CODE_LENGTH))


def _insert(conn: sqlite3.Connection, data: rules.ReservationInput, start: datetime,
            end: datetime) -> str:
    while True:
        code = new_reservation_code()
        try:
            conn.execute(
                "INSERT INTO reservations (reservation_code, resource_id, start_at, end_at,"
                " customer_name) VALUES (?, ?, ?, ?, ?)",
                (code, data.resource_id, start.isoformat(), end.isoformat(), data.customer_name),
            )
            return code
        except sqlite3.IntegrityError as exc:
            # 겹침 트리거가 거부하면 OVERLAP(409)이다. (D-032)
            if str(exc) == "OVERLAP":
                raise ApiError(409, "OVERLAP", "같은 자원에 이미 예약된 시간과 겹칩니다.") from None
            # 코드가 이미 있으면 다시 만든다. 그 밖의 오류는 그대로 올린다. (D-033)
            if "reservation_code" not in str(exc):
                raise


def create_reservation(conn: sqlite3.Connection, data: rules.ReservationInput,
                       start: datetime, end: datetime) -> dict:
    """판정 순서: 쓰기 단위 시작 → 자원 존재 → 지나간 시각 → C-1 → 저장 (D-028, D-035)"""
    with write_unit(conn):
        resource = conn.execute(
            "SELECT name FROM resources WHERE id = ?", (data.resource_id,)
        ).fetchone()
        if resource is None:
            raise resource_not_found()
        rules.check_not_past(start, rules.now_seoul())
        day_hours = load_operating_hours(conn, data.resource_id)[WEEKDAYS[start.weekday()]]
        rules.check_operating_hours(day_hours, start, end)
        # C-2 이용시간(R-003)은 이번 범위가 아니어서 아직 판정하지 않는다.
        # C-3 겹침은 저장 단계의 트리거가 판정한다.
        code = _insert(conn, data, start, end)

    return {
        "reservation_code": code,
        "resource_id": data.resource_id,
        "resource_name": resource["name"],
        "start_at": start.isoformat(),
        "end_at": end.isoformat(),
        "status": "reserved",
        "customer_name": data.customer_name,
    }
