from fastapi import APIRouter

from app.services import resources as service
from app.storage.db import connect
from app.validation.resource_input import ResourceInput, check_resource_input

# 운영자 역할 검사(C-5, R-011)는 이번 범위가 아니어서 아직 없다.
router = APIRouter(prefix="/resources")


@router.get("")
def list_resources():
    # 토큰이 없는 요청은 고객 요청이므로 id·name만 응답한다. (API-SPEC 4.1)
    conn = connect()
    try:
        return {"resources": service.list_resource_names(conn)}
    finally:
        conn.close()


@router.post("", status_code=201)
def create_resource(data: ResourceInput):
    check_resource_input(data)
    conn = connect()
    try:
        return service.create_resource(conn, data)
    finally:
        conn.close()


@router.put("/{resource_id}")
def update_resource(resource_id: int, data: ResourceInput):
    check_resource_input(data)
    conn = connect()
    try:
        return service.update_resource(conn, resource_id, data)
    finally:
        conn.close()
