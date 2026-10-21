from fastapi import APIRouter

from app.services import reservations as service
from app.storage.db import connect
from app.validation.reservation_rules import ReservationInput, check_reservation_input

router = APIRouter(prefix="/reservations")


@router.post("", status_code=201)
def create_reservation(data: ReservationInput):
    start, end = check_reservation_input(data)
    conn = connect()
    try:
        return service.create_reservation(conn, data, start, end)
    finally:
        conn.close()
