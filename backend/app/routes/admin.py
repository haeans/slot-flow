from fastapi import APIRouter, Depends

from app.routes.deps import admin_account
from app.services import accounts
from app.storage.db import connect

# 운영자 관리. 관리자만 쓴다. 운영자는 내부 키 대신 예약 주소명으로 가리킨다. (D-043, D-067)
router = APIRouter(prefix="/admin", dependencies=[Depends(admin_account)])


@router.get("/operators")
def list_operators():
    conn = connect()
    try:
        return {"operators": accounts.list_operators(conn)}
    finally:
        conn.close()


def _set_status(booking_slug: str, status: str) -> dict:
    conn = connect()
    try:
        return {"operator": accounts.set_operator_status(conn, booking_slug, status)}
    finally:
        conn.close()


@router.post("/operators/{booking_slug}/approve")
def approve_operator(booking_slug: str):
    return _set_status(booking_slug, "approved")


@router.post("/operators/{booking_slug}/suspend")
def suspend_operator(booking_slug: str):
    return _set_status(booking_slug, "suspended")
