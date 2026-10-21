import re
from datetime import datetime, timedelta, timezone

from pydantic import BaseModel, StrictInt, StrictStr

from app.errors import ApiError, invalid_input

# 한국은 서머타임이 없어 고정 오프셋 +09:00 하나로 충분하다. (D-022)
KST = timezone(timedelta(hours=9))

# YYYY-MM-DDTHH:MM:SS+09:00 (D-027)
_DATETIME = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\+09:00$")


class ReservationInput(BaseModel):
    resource_id: StrictInt
    start_at: StrictStr
    end_at: StrictStr
    customer_name: StrictStr


def now_seoul() -> datetime:
    return datetime.now(KST)


def parse_datetime(value: str) -> datetime:
    """+09:00 고정, 실제로 있는 시각, 30분 단위만 받는다. (D-018, D-024, D-027)"""
    if not _DATETIME.match(value):
        raise invalid_input("시각은 YYYY-MM-DDTHH:MM:SS+09:00 형식이어야 합니다.")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        raise invalid_input("시각은 YYYY-MM-DDTHH:MM:SS+09:00 형식이어야 합니다.") from None
    if parsed.minute not in (0, 30) or parsed.second != 0:
        raise invalid_input("시각은 30분 단위여야 합니다.")
    return parsed


def check_reservation_input(data: ReservationInput) -> tuple[datetime, datetime]:
    """입력 형식 검사. 쓰기 단위 밖에서 한다. (D-028, D-035)"""
    start = parse_datetime(data.start_at)
    end = parse_datetime(data.end_at)
    if start >= end:
        raise invalid_input("시작 시각은 종료 시각보다 빨라야 합니다.")
    return start, end


def check_not_past(start: datetime, now: datetime) -> None:
    """시작 시각이 이미 지났으면 거부한다. (D-014, D-024)"""
    if start < now:
        raise ApiError(422, "PAST_TIME", "이미 지난 시각은 예약할 수 없습니다.")


def check_operating_hours(day_hours: dict | None, start: datetime, end: datetime) -> None:
    """C-1. 예약 전체가 그 요일의 운영시간 안에 있어야 한다. (D-011, D-019)"""
    outside = ApiError(422, "OUTSIDE_OPERATING_HOURS", "운영시간 밖의 시간대는 예약할 수 없습니다.")
    if day_hours is None or start.date() != end.date():
        raise outside
    if start.strftime("%H:%M") < day_hours["open"] or end.strftime("%H:%M") > day_hours["close"]:
        raise outside
