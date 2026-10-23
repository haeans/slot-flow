import re
import sqlite3
from datetime import date, timedelta

from app.errors import invalid_input, resource_not_found
from app.services.resources import bookable_resource, load_operating_hours
from app.validation.resource_input import WEEKDAYS

_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def parse_date(value: str) -> date:
    """YYYY-MM-DD이고 실제로 있는 날짜만 받는다. (D-027)"""
    if not _DATE.match(value):
        raise invalid_input("날짜는 YYYY-MM-DD 형식이어야 합니다.")
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise invalid_input("날짜는 YYYY-MM-DD 형식이어야 합니다.") from None


def to_minutes(hhmm: str) -> int:
    hours, minutes = hhmm.split(":")
    return int(hours) * 60 + int(minutes)


def to_datetime_text(day: date, minutes: int) -> str:
    """저장·응답 형식의 시각 YYYY-MM-DDTHH:MM:00+09:00 (D-027, D-030)"""
    return f"{day.isoformat()}T{minutes // 60:02d}:{minutes % 60:02d}:00+09:00"


def list_slots(conn: sqlite3.Connection, resource_id: int, day: date) -> dict:
    """그날 요일의 운영시간을 30분 칸으로 나눈다. (API-SPEC 4.2, D-020)"""
    if bookable_resource(conn, resource_id) is None:
        raise resource_not_found()
    hours = load_operating_hours(conn, resource_id)[WEEKDAYS[day.weekday()]]
    # 그날 시작하는 "예약됨" 예약. 시각은 고정 형식이라 문자열 비교가 곧 시간 비교다. (D-030)
    taken = conn.execute(
        "SELECT start_at, end_at FROM reservations WHERE resource_id = ? AND status = 'reserved'"
        " AND start_at >= ? AND start_at < ?",
        (resource_id, to_datetime_text(day, 0),
         to_datetime_text(day + timedelta(days=1), 0)),
    ).fetchall()
    slots = []
    if hours is not None:
        for start in range(to_minutes(hours["open"]), to_minutes(hours["close"]), 30):
            start_at = to_datetime_text(day, start)
            end_at = to_datetime_text(day, start + 30)
            reserved = any(r["start_at"] < end_at and start_at < r["end_at"] for r in taken)
            slots.append({
                "start_at": start_at,
                "end_at": end_at,
                "status": "reserved" if reserved else "available",
            })
    return {"resource_id": resource_id, "date": day.isoformat(), "slots": slots}
