import re

from pydantic import BaseModel, StrictInt, StrictStr

from app.errors import invalid_input

WEEKDAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")

# HH:MM, 30분 단위, 00:00~23:30 (D-031)
_HOURS_TIME = re.compile(r"^([01][0-9]|2[0-3]):(00|30)$")


class DayHours(BaseModel):
    open: StrictStr
    close: StrictStr


class ResourceInput(BaseModel):
    name: StrictStr
    operating_hours: dict[str, DayHours | None]
    min_duration_minutes: StrictInt
    max_duration_minutes: StrictInt
    cancel_deadline_hours: StrictInt


def check_resource_input(data: ResourceInput) -> None:
    """자원 입력의 거부 기준 (D-036). 걸리면 INVALID_INPUT(400)."""
    if set(data.operating_hours) != set(WEEKDAYS):
        raise invalid_input("운영시간에는 mon~sun 일곱 요일이 모두 있어야 합니다. 운영하지 않는 요일은 null로 보냅니다.")
    for day in data.operating_hours.values():
        if day is None:
            continue
        if not (_HOURS_TIME.match(day.open) and _HOURS_TIME.match(day.close)):
            raise invalid_input("운영시간은 00:00~23:30 사이의 30분 단위 HH:MM이어야 합니다.")
        if day.open >= day.close:
            raise invalid_input("운영 시작 시각은 종료 시각보다 빨라야 합니다.")

    for value in (data.min_duration_minutes, data.max_duration_minutes):
        if value < 30 or value % 30 != 0:
            raise invalid_input("최소·최대 이용시간은 30분 단위이고 30분 이상이어야 합니다.")
    if data.min_duration_minutes > data.max_duration_minutes:
        raise invalid_input("최소 이용시간이 최대 이용시간보다 클 수 없습니다.")
