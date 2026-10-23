from fastapi import APIRouter, Request

from app.errors import invalid_input
from app.routes.deps import session_account
from app.services import reservations as service
from app.storage.db import connect
from app.validation.reservation_rules import ReservationInput, check_reservation_input

router = APIRouter(prefix="/reservations")


@router.post("", status_code=201)
def create_reservation(data: ReservationInput, request: Request):
    start, end = check_reservation_input(data)
    # 유효한 회원 고객 세션이면 회원 예약, 아니면 비회원 예약이다. 운영자·관리자 세션도 비회원이다. (D-051, D-061)
    account = session_account(request)
    member = account if account is not None and account["role"] == "customer" else None
    # 회원은 이름을 생략하면 계정 이름을 쓴다. 비회원은 이름이 필요하다. (D-068)
    customer_name = data.customer_name or (member["name"] if member else None)
    if not customer_name:
        raise invalid_input("이름을 입력해 주세요.")
    conn = connect()
    try:
        return service.create_reservation(
            conn, data, start, end, customer_name, member["id"] if member else None
        )
    finally:
        conn.close()
