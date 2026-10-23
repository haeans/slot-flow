import secrets
import sqlite3
from datetime import datetime

from app.errors import ApiError, resource_not_found
from app.services.resources import bookable_resource, load_operating_hours
from app.storage.db import write_unit
from app.validation import reservation_rules as rules
from app.validation.resource_input import WEEKDAYS

# 헷갈리는 0 O 1 I L을 뺀 31자 (D-033)
CODE_ALPHABET = "23456789ABCDEFGHJKMNPQRSTUVWXYZ"
CODE_LENGTH = 10


def new_reservation_code() -> str:
    return "".join(secrets.choice(CODE_ALPHABET) for _ in range(CODE_LENGTH))


def _insert(conn: sqlite3.Connection, data: rules.ReservationInput, start: datetime,
            end: datetime, customer_name: str, customer_account_id: int | None) -> str:
    while True:
        code = new_reservation_code()
        try:
            conn.execute(
                "INSERT INTO reservations (reservation_code, resource_id, start_at, end_at,"
                " customer_name, customer_account_id) VALUES (?, ?, ?, ?, ?, ?)",
                (code, data.resource_id, start.isoformat(), end.isoformat(), customer_name,
                 customer_account_id),
            )
            return code
        except sqlite3.IntegrityError as exc:
            # 겹침 트리거가 거부하면 OVERLAP(409)이다. (D-032)
            if str(exc) == "OVERLAP":
                raise ApiError(409, "OVERLAP", "같은 자원에 이미 예약된 시간과 겹칩니다.") from None
            # 코드가 이미 있으면 다시 만든다. 그 밖의 오류는 그대로 올린다. (D-033)
            if "reservation_code" not in str(exc):
                raise


def reservation_object(row: sqlite3.Row) -> dict:
    # 회원 예약인지 담아, 회원이 모르는 사이에 비회원 예약이 되는 일을 화면에서 알 수 있게 한다. (D-051)
    return {
        "reservation_code": row["reservation_code"],
        "resource_id": row["resource_id"],
        "resource_name": row["resource_name"],
        "start_at": row["start_at"],
        "end_at": row["end_at"],
        "status": row["status"],
        "customer_name": row["customer_name"],
        "is_member": row["customer_account_id"] is not None,
    }


def list_member_reservations(conn: sqlite3.Connection, account_id: int) -> list[dict]:
    """로그인한 회원 본인의 예약. 취소된 예약도 담는다. (D-004, D-045)"""
    rows = conn.execute(
        "SELECT v.*, r.name AS resource_name FROM reservations v"
        " JOIN resources r ON r.id = v.resource_id"
        " WHERE v.customer_account_id = ? ORDER BY v.start_at, v.id",
        (account_id,),
    ).fetchall()
    return [reservation_object(row) for row in rows]


def create_reservation(conn: sqlite3.Connection, data: rules.ReservationInput,
                       start: datetime, end: datetime, customer_name: str | None = None,
                       customer_account_id: int | None = None) -> dict:
    """판정 순서: 쓰기 단위 시작 → 자원 존재 → 지나간 시각 → C-1 → 저장 (D-028, D-035)
    회원 예약이면 customer_account_id 에 계정을 연결한다. (D-045)"""
    customer_name = customer_name or data.customer_name
    with write_unit(conn):
        resource = bookable_resource(conn, data.resource_id)
        if resource is None:
            raise resource_not_found()
        rules.check_not_past(start, rules.now_seoul())
        day_hours = load_operating_hours(conn, data.resource_id)[WEEKDAYS[start.weekday()]]
        rules.check_operating_hours(day_hours, start, end)
        # C-2 이용시간(R-003)은 이번 범위가 아니어서 아직 판정하지 않는다.
        # C-3 겹침은 저장 단계의 트리거가 판정한다.
        code = _insert(conn, data, start, end, customer_name, customer_account_id)

    return {
        "reservation_code": code,
        "resource_id": data.resource_id,
        "resource_name": resource["name"],
        "start_at": start.isoformat(),
        "end_at": end.isoformat(),
        "status": "reserved",
        "customer_name": customer_name,
        "is_member": customer_account_id is not None,
    }
