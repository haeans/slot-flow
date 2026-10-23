from conftest import add_operator, login_as, resource_body

from app.storage import db

# 역할·소유 검사 (API-SPEC-CHANGE 3절, D-043, D-044, D-052, D-065)
MONDAY = "2026-11-02"


def set_status(email, status):
    conn = db.connect()
    conn.execute("UPDATE accounts SET operator_status = ? WHERE email = ?", (status, email))
    conn.close()


def code_of(res):
    return res.status_code, res.json()["error"]["code"]


def test_operator_requests_need_session(anon_client):
    assert code_of(anon_client.post("/resources", json=resource_body())) == (401, "UNAUTHENTICATED")
    assert code_of(anon_client.put("/resources/1", json=resource_body())) == (401, "UNAUTHENTICATED")
    assert code_of(anon_client.get("/resources")) == (401, "UNAUTHENTICATED")


def test_customer_is_forbidden(client):
    client.post("/auth/signup", json={"email": "guest@example.com", "password": "guest-pass-1",
                                      "role": "customer", "name": "홍길동"})
    login_as(client, "guest@example.com", "guest-pass-1")
    assert code_of(client.post("/resources", json=resource_body())) == (403, "FORBIDDEN")


def test_pending_and_suspended_operators_are_refused(client):
    add_operator(client, "wait@example.com", "wait-studio", status="pending")
    login_as(client, "wait@example.com")
    assert code_of(client.post("/resources", json=resource_body())) == (403, "OPERATOR_NOT_APPROVED")
    # 정지와 요청이 거의 같은 때 들어온 경우 (D-053)
    set_status("wait@example.com", "suspended")
    assert code_of(client.post("/resources", json=resource_body())) == (403, "OPERATOR_SUSPENDED")


def test_owner_is_the_requesting_operator(operator_client):
    rid = operator_client.post("/resources", json=resource_body()).json()["id"]
    conn = db.connect()
    owner = conn.execute(
        "SELECT a.email FROM resources r JOIN accounts a ON a.id = r.owner_account_id WHERE r.id = ?",
        (rid,),
    ).fetchone()["email"]
    conn.close()
    assert owner == "op@example.com"


def test_other_operators_resource_is_not_found(operator_client, anon_client):
    rid = operator_client.post("/resources", json=resource_body()).json()["id"]
    add_operator(anon_client, "other@example.com", "other-studio")
    login_as(anon_client, "other@example.com")
    assert anon_client.get("/resources").json() == {"resources": []}
    assert code_of(anon_client.put(f"/resources/{rid}", json=resource_body())) == (404, "RESOURCE_NOT_FOUND")


def test_customer_lists_resources_by_booking_slug(operator_client, anon_client):
    created = operator_client.post("/resources", json=resource_body()).json()
    res = anon_client.get("/resources", params={"operator": "op-studio"})
    assert res.status_code == 200
    # 고객에게는 id·name 만 응답한다. (API-SPEC 4.1)
    assert res.json() == {"resources": [{"id": created["id"], "name": created["name"]}]}
    assert code_of(anon_client.get("/resources", params={"operator": "nobody"})) == (404, "OPERATOR_NOT_FOUND")


def test_pending_operator_slug_is_not_found(client, anon_client):
    add_operator(client, "wait@example.com", "wait-studio", status="pending")
    assert code_of(anon_client.get("/resources", params={"operator": "wait-studio"})) == (404, "OPERATOR_NOT_FOUND")


def test_suspended_operator_takes_no_new_reservations(operator_client, anon_client):
    rid = operator_client.post("/resources", json=resource_body()).json()["id"]
    booking = {"resource_id": rid, "start_at": f"{MONDAY}T10:00:00+09:00",
               "end_at": f"{MONDAY}T11:00:00+09:00", "customer_name": "홍길동"}
    code = anon_client.post("/reservations", json=booking).json()["reservation_code"]

    set_status("op@example.com", "suspended")
    # 예약 주소·칸·새 예약은 막고, 이미 받은 예약은 그대로 둔다. (D-065)
    assert code_of(anon_client.get("/resources", params={"operator": "op-studio"})) == (404, "OPERATOR_NOT_FOUND")
    assert code_of(anon_client.get(f"/resources/{rid}/slots", params={"date": MONDAY})) == (404, "RESOURCE_NOT_FOUND")
    later = {**booking, "start_at": f"{MONDAY}T11:00:00+09:00", "end_at": f"{MONDAY}T11:30:00+09:00"}
    assert code_of(anon_client.post("/reservations", json=later)) == (404, "RESOURCE_NOT_FOUND")
    conn = db.connect()
    row = conn.execute("SELECT status FROM reservations WHERE reservation_code = ?", (code,)).fetchone()
    conn.close()
    assert row["status"] == "reserved"
