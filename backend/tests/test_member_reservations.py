from conftest import login_as, resource_body

from app.services import sessions
from app.storage import db

# 회원 예약과 내 예약 목록 (D-045, D-051, D-061, D-068, D-069)
MONDAY = "2026-11-02"
PASSWORD = "member-pass-1"


def at(hhmm):
    return f"{MONDAY}T{hhmm}:00+09:00"


def booking(rid, start, end, **extra):
    return {"resource_id": rid, "start_at": at(start), "end_at": at(end), **extra}


def make_member(client, email="member@example.com", name="김회원"):
    client.post("/auth/signup", json={"email": email, "password": PASSWORD, "role": "customer", "name": name})
    login_as(client, email, PASSWORD)


def account_id_of(code):
    conn = db.connect()
    try:
        return conn.execute(
            "SELECT customer_account_id FROM reservations WHERE reservation_code = ?", (code,)
        ).fetchone()[0]
    finally:
        conn.close()


def test_member_reservation_uses_account_name(operator_client, anon_client):
    rid = operator_client.post("/resources", json=resource_body()).json()["id"]
    make_member(anon_client)
    res = anon_client.post("/reservations", json=booking(rid, "10:00", "11:00"))
    assert res.status_code == 201
    body = res.json()
    assert body["customer_name"] == "김회원"
    assert body["is_member"] is True
    assert account_id_of(body["reservation_code"]) is not None


def test_member_can_give_another_name(operator_client, anon_client):
    rid = operator_client.post("/resources", json=resource_body()).json()["id"]
    make_member(anon_client)
    res = anon_client.post("/reservations", json=booking(rid, "10:00", "11:00", customer_name="대리인"))
    assert res.json()["customer_name"] == "대리인"
    assert res.json()["is_member"] is True


def test_guest_needs_name(operator_client, anon_client):
    rid = operator_client.post("/resources", json=resource_body()).json()["id"]
    res = anon_client.post("/reservations", json=booking(rid, "10:00", "11:00"))
    assert res.status_code == 400
    assert res.json()["error"]["code"] == "INVALID_INPUT"
    ok = anon_client.post("/reservations", json=booking(rid, "10:00", "11:00", customer_name="홍길동"))
    assert ok.json()["is_member"] is False
    assert account_id_of(ok.json()["reservation_code"]) is None


def test_operator_session_books_as_guest(operator_client):
    rid = operator_client.post("/resources", json=resource_body()).json()["id"]
    res = operator_client.post("/reservations", json=booking(rid, "10:00", "11:00", customer_name="손님"))
    assert res.status_code == 201
    assert res.json()["is_member"] is False


def test_invalid_session_books_as_guest(operator_client, anon_client):
    rid = operator_client.post("/resources", json=resource_body()).json()["id"]
    anon_client.cookies.set(sessions.COOKIE_NAME, "not-a-real-token")
    res = anon_client.post("/reservations", json=booking(rid, "10:00", "11:00", customer_name="홍길동"))
    assert res.status_code == 201
    assert res.json()["is_member"] is False


def test_my_reservations_lists_only_own(operator_client, anon_client):
    rid = operator_client.post("/resources", json=resource_body()).json()["id"]
    operator_client.post("/reservations", json=booking(rid, "11:30", "12:00", customer_name="비회원"))
    make_member(anon_client, "other@example.com", "다른회원")
    anon_client.post("/reservations", json=booking(rid, "11:00", "11:30"))
    make_member(anon_client)
    later = anon_client.post("/reservations", json=booking(rid, "10:30", "11:00")).json()
    first = anon_client.post("/reservations", json=booking(rid, "10:00", "10:30")).json()

    res = anon_client.get("/me/reservations")
    assert res.status_code == 200
    assert res.json() == {"reservations": [first, later]}


def test_my_reservations_need_member_session(operator_client, anon_client):
    assert anon_client.get("/me/reservations").status_code == 401
    res = operator_client.get("/me/reservations")
    assert res.status_code == 403
    assert res.json()["error"]["code"] == "FORBIDDEN"


def test_empty_list(anon_client):
    make_member(anon_client)
    assert anon_client.get("/me/reservations").json() == {"reservations": []}
