from conftest import resource_body

from app.services.reservations import CODE_ALPHABET

MONDAY = "2026-11-02"


def at(day: str, hhmm: str) -> str:
    return f"{day}T{hhmm}:00+09:00"


def make_resource(client) -> int:
    return client.post("/resources", json=resource_body()).json()["id"]  # 월 10:00~12:00


def reserve(client, resource_id, start, end, name="홍길동"):
    return client.post("/reservations", json={
        "resource_id": resource_id, "start_at": start, "end_at": end, "customer_name": name,
    })


def test_create_reservation(client):
    rid = make_resource(client)
    res = reserve(client, rid, at(MONDAY, "10:00"), at(MONDAY, "11:00"))
    assert res.status_code == 201
    body = res.json()
    assert body["status"] == "reserved"
    assert body["resource_name"] == "공방 작업대 A"
    assert body["start_at"] == at(MONDAY, "10:00")
    assert body["customer_name"] == "홍길동"
    code = body["reservation_code"]
    assert len(code) == 10 and all(c in CODE_ALPHABET for c in code)

    slots = client.get(f"/resources/{rid}/slots", params={"date": MONDAY}).json()["slots"]
    assert [s["status"] for s in slots] == ["reserved", "reserved", "available", "available"]
    assert "customer_name" not in slots[0] and "reservation_code" not in slots[0]


def test_past_time_is_rejected(client):
    rid = make_resource(client)
    # 지금(FIXED_NOW)은 2026-10-21 12:00. 그 전 월요일 2026-10-19는 지났다.
    res = reserve(client, rid, at("2026-10-19", "10:00"), at("2026-10-19", "11:00"))
    assert res.status_code == 422
    assert res.json()["error"]["code"] == "PAST_TIME"


def test_outside_operating_hours_is_rejected(client):
    rid = make_resource(client)
    for start, end in (
        (at(MONDAY, "11:30"), at(MONDAY, "12:30")),        # 일부만 걸침
        (at(MONDAY, "09:00"), at(MONDAY, "10:00")),        # 시작 전
        (at("2026-11-03", "10:00"), at("2026-11-03", "11:00")),  # 운영하지 않는 화요일
    ):
        res = reserve(client, rid, start, end)
        assert res.status_code == 422
        assert res.json()["error"]["code"] == "OUTSIDE_OPERATING_HOURS"


def test_invalid_input_is_rejected(client):
    rid = make_resource(client)
    for start, end in (
        (at(MONDAY, "10:15"), at(MONDAY, "11:00")),          # 30분 단위 아님
        ("2026-11-02T10:00:00Z", at(MONDAY, "11:00")),       # +09:00 아님
        (at(MONDAY, "11:00"), at(MONDAY, "10:00")),          # 시작 > 종료
        (at(MONDAY, "10:00"), at(MONDAY, "10:00")),          # 시작 = 종료
    ):
        res = reserve(client, rid, start, end)
        assert res.status_code == 400
        assert res.json()["error"]["code"] == "INVALID_INPUT"


def test_missing_resource_and_order(client):
    res = reserve(client, 999, at(MONDAY, "10:00"), at(MONDAY, "11:00"))
    assert res.status_code == 404
    assert res.json()["error"]["code"] == "RESOURCE_NOT_FOUND"

    # 지나간 시각이면서 운영시간 밖이면 먼저 걸린 PAST_TIME 하나만 응답한다. (D-028)
    rid = make_resource(client)
    res = reserve(client, rid, at("2026-10-20", "10:00"), at("2026-10-20", "11:00"))
    assert res.json()["error"]["code"] == "PAST_TIME"
