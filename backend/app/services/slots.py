import re
import sqlite3
from datetime import date

from app.errors import invalid_input, resource_not_found
from app.services.resources import load_operating_hours, resource_exists
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
    if not resource_exists(conn, resource_id):
        raise resource_not_found()
    hours = load_operating_hours(conn, resource_id)[WEEKDAYS[day.weekday()]]
    slots = []
    if hours is not None:
        for start in range(to_minutes(hours["open"]), to_minutes(hours["close"]), 30):
            slots.append({
                "start_at": to_datetime_text(day, start),
                "end_at": to_datetime_text(day, start + 30),
                "status": "available",
            })
    return {"resource_id": resource_id, "date": day.isoformat(), "slots": slots}
