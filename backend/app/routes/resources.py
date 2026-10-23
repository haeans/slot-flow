from fastapi import APIRouter, Depends, Request

from app.errors import ApiError
from app.routes.deps import approved_operator
from app.services import resources as service
from app.services import slots as slot_service
from app.storage.db import connect
from app.validation.resource_input import ResourceInput, check_resource_input

router = APIRouter(prefix="/resources")


@router.get("")
def list_resources(request: Request, operator: str | None = None):
    """operator(예약 주소명)가 있으면 고객 조회, 없으면 운영자 자기 자원 조회다. (API-SPEC-CHANGE 3절)"""
    if operator is None:
        account = approved_operator(request)
        conn = connect()
        try:
            return {"resources": service.list_resources(conn, account["id"])}
        finally:
            conn.close()
    # 고객 조회는 세션을 보지 않고 id·name 만 응답한다. (API-SPEC 4.1)
    conn = connect()
    try:
        owner = service.find_operator_by_slug(conn, operator)
        if owner is None:
            raise ApiError(404, "OPERATOR_NOT_FOUND", "예약 주소를 찾을 수 없습니다.")
        return {"resources": service.list_resource_names(conn, owner["id"])}
    finally:
        conn.close()


@router.get("/{resource_id}/slots")
def list_slots(resource_id: int, date: str):
    day = slot_service.parse_date(date)
    conn = connect()
    try:
        return slot_service.list_slots(conn, resource_id, day)
    finally:
        conn.close()


@router.post("", status_code=201)
def create_resource(data: ResourceInput, account=Depends(approved_operator)):
    check_resource_input(data)
    conn = connect()
    try:
        return service.create_resource(conn, data, account["id"])
    finally:
        conn.close()


@router.put("/{resource_id}")
def update_resource(resource_id: int, data: ResourceInput, account=Depends(approved_operator)):
    check_resource_input(data)
    conn = connect()
    try:
        return service.update_resource(conn, resource_id, data, account["id"])
    finally:
        conn.close()
