from pydantic import BaseModel, StrictInt, StrictStr

from app.errors import invalid_input


class ResourceInput(BaseModel):
    name: StrictStr
    min_duration_minutes: StrictInt
    max_duration_minutes: StrictInt
    cancel_deadline_hours: StrictInt


def check_resource_input(data: ResourceInput) -> None:
    """자원 입력의 거부 기준 (D-036). 걸리면 INVALID_INPUT(400)."""
    for value in (data.min_duration_minutes, data.max_duration_minutes):
        if value < 30 or value % 30 != 0:
            raise invalid_input("최소·최대 이용시간은 30분 단위이고 30분 이상이어야 합니다.")
    if data.min_duration_minutes > data.max_duration_minutes:
        raise invalid_input("최소 이용시간이 최대 이용시간보다 클 수 없습니다.")
