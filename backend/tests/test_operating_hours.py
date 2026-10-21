from conftest import resource_body, week_hours

MONDAY = "2026-11-02"
TUESDAY = "2026-11-03"


def test_slots_follow_operating_hours(client):
    created = client.post("/resources", json=resource_body()).json()
    assert created["operating_hours"]["mon"] == {"open": "10:00", "close": "12:00"}
    assert created["operating_hours"]["sun"] is None

    res = client.get(f"/resources/{created['id']}/slots", params={"date": MONDAY})
    assert res.status_code == 200
    slots = res.json()["slots"]
    assert [s["start_at"] for s in slots] == [
        "2026-11-02T10:00:00+09:00",
        "2026-11-02T10:30:00+09:00",
        "2026-11-02T11:00:00+09:00",
        "2026-11-02T11:30:00+09:00",
    ]
    assert slots[-1]["end_at"] == "2026-11-02T12:00:00+09:00"
    assert all(s["status"] == "available" for s in slots)


def test_invalid_operating_hours_are_rejected(client):
    missing_day = week_hours()
    del missing_day["sun"]
    for hours in (
        missing_day,
        week_hours(mon={"open": "12:00", "close": "12:00"}),
        week_hours(mon={"open": "13:00", "close": "12:00"}),
        week_hours(mon={"open": "10:15", "close": "12:00"}),
        week_hours(mon={"open": "10:00", "close": "24:00"}),
    ):
        res = client.post("/resources", json=resource_body(operating_hours=hours))
        assert res.status_code == 400
        assert res.json()["error"]["code"] == "INVALID_INPUT"
    assert client.get("/resources").json() == {"resources": []}


def test_closed_day_has_no_slots(client):
    created = client.post("/resources", json=resource_body()).json()
    res = client.get(f"/resources/{created['id']}/slots", params={"date": TUESDAY})
    assert res.status_code == 200
    assert res.json() == {"resource_id": created["id"], "date": TUESDAY, "slots": []}


def test_update_replaces_operating_hours(client):
    created = client.post("/resources", json=resource_body()).json()
    hours = week_hours(tue={"open": "09:00", "close": "10:00"})
    updated = client.put(f"/resources/{created['id']}", json=resource_body(operating_hours=hours))
    assert updated.status_code == 200
    assert updated.json()["operating_hours"] == hours

    monday = client.get(f"/resources/{created['id']}/slots", params={"date": MONDAY}).json()
    assert monday["slots"] == []


def test_slots_reject_bad_date_and_missing_resource(client):
    created = client.post("/resources", json=resource_body()).json()
    for bad in ("2026-13-01", "20261102", "2026-11-31"):
        res = client.get(f"/resources/{created['id']}/slots", params={"date": bad})
        assert res.status_code == 400
        assert res.json()["error"]["code"] == "INVALID_INPUT"
    assert client.get(f"/resources/{created['id']}/slots").status_code == 400

    res = client.get("/resources/999/slots", params={"date": MONDAY})
    assert res.status_code == 404
    assert res.json()["error"]["code"] == "RESOURCE_NOT_FOUND"
