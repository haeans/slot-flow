import sqlite3
import threading

import pytest
from conftest import resource_body
from test_reservations import MONDAY, at, reserve

from app.errors import ApiError
from app.services import reservations as service
from app.storage.db import connect
from app.validation.reservation_rules import ReservationInput, check_reservation_input


@pytest.fixture
def client(operator_client):
    # 이 파일의 요청은 승인된 운영자로 로그인한 채로 보낸다. (D-043, D-044)
    return operator_client


def make_resource(client, name="공방 작업대 A") -> int:
    return client.post("/resources", json=resource_body(name=name)).json()["id"]


def test_overlap_rejected_but_touching_boundary_allowed(client):
    rid = make_resource(client)
    assert reserve(client, rid, at(MONDAY, "10:00"), at(MONDAY, "11:00")).status_code == 201

    res = reserve(client, rid, at(MONDAY, "10:30"), at(MONDAY, "11:30"))
    assert res.status_code == 409
    assert res.json() == {
        "error": {"code": "OVERLAP", "message": "같은 자원에 이미 예약된 시간과 겹칩니다."}
    }

    # 앞 예약의 끝과 뒤 예약의 시작이 같으면 겹침이 아니다. (D-009)
    assert reserve(client, rid, at(MONDAY, "11:00"), at(MONDAY, "12:00")).status_code == 201


def test_same_time_on_other_resource_is_independent(client):
    a = make_resource(client, "작업대 A")
    b = make_resource(client, "작업대 B")
    assert reserve(client, a, at(MONDAY, "10:00"), at(MONDAY, "11:00")).status_code == 201
    assert reserve(client, b, at(MONDAY, "10:00"), at(MONDAY, "11:00")).status_code == 201


def test_concurrent_requests_only_one_wins(client):
    rid = make_resource(client)
    data = ReservationInput(resource_id=rid, start_at=at(MONDAY, "10:00"),
                            end_at=at(MONDAY, "11:00"), customer_name="동시")
    start, end = check_reservation_input(data)
    barrier = threading.Barrier(2)
    outcomes = []

    def attempt():
        conn = connect()  # 요청마다 따로 연결한다
        try:
            barrier.wait()
            service.create_reservation(conn, data, start, end)
            outcomes.append("created")
        except ApiError as exc:
            outcomes.append(exc.code)
        finally:
            conn.close()

    threads = [threading.Thread(target=attempt) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert sorted(outcomes) == ["OVERLAP", "created"]
    conn = connect()
    count = conn.execute(
        "SELECT count(*) FROM reservations WHERE resource_id = ? AND status = 'reserved'", (rid,)
    ).fetchone()[0]
    conn.close()
    assert count == 1


def test_trigger_blocks_overlap_without_service(client):
    # 서비스 코드를 거치지 않고 직접 넣어도 저장소가 막는다. (D-003)
    rid = make_resource(client)
    conn = connect()
    insert = ("INSERT INTO reservations (reservation_code, resource_id, start_at, end_at,"
              " customer_name) VALUES (?, ?, ?, ?, ?)")
    conn.execute(insert, ("AAAAAAAAAA", rid, at(MONDAY, "10:00"), at(MONDAY, "11:00"), "가"))
    with pytest.raises(sqlite3.IntegrityError, match="OVERLAP"):
        conn.execute(insert, ("BBBBBBBBBB", rid, at(MONDAY, "10:30"), at(MONDAY, "11:00"), "나"))
    # 취소된 예약은 비교하지 않는다. (D-010)
    conn.execute("UPDATE reservations SET status = 'cancelled' WHERE reservation_code = 'AAAAAAAAAA'")
    conn.execute(insert, ("CCCCCCCCCC", rid, at(MONDAY, "10:00"), at(MONDAY, "11:00"), "다"))
    conn.close()
