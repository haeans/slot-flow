from fastapi import APIRouter, Request

from app.errors import ApiError
from app.routes.deps import session_account
from app.services import reservations as service
from app.services import sessions
from app.storage.db import connect

router = APIRouter(prefix="/me")


@router.get("/reservations")
def my_reservations(request: Request):
    """로그인한 회원 고객 본인의 예약 목록. 비회원 예약은 연결하지 않는다. (D-045, D-069)"""
    account = session_account(request)
    if account is None:
        raise sessions.unauthenticated()
    if account["role"] != "customer":
        raise ApiError(403, "FORBIDDEN", "회원 고객만 쓸 수 있습니다.")
    conn = connect()
    try:
        return {"reservations": service.list_member_reservations(conn, account["id"])}
    finally:
        conn.close()
