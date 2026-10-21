from conftest import resource_body


def test_create_resource_appears_in_list(client):
    res = client.post("/resources", json=resource_body())
    assert res.status_code == 201
    created = res.json()
    assert created["name"] == "공방 작업대 A"
    assert created["max_duration_minutes"] == 120

    listed = client.get("/resources").json()
    assert listed == {"resources": [{"id": created["id"], "name": "공방 작업대 A"}]}


def test_invalid_duration_is_rejected(client):
    for body in (
        resource_body(min_duration_minutes=45),
        resource_body(min_duration_minutes=150, max_duration_minutes=120),
        resource_body(max_duration_minutes=0),
    ):
        res = client.post("/resources", json=body)
        assert res.status_code == 400
        assert res.json()["error"]["code"] == "INVALID_INPUT"
    assert client.get("/resources").json() == {"resources": []}


def test_update_missing_resource_is_not_found(client):
    res = client.put("/resources/999", json=resource_body())
    assert res.status_code == 404
    assert res.json()["error"]["code"] == "RESOURCE_NOT_FOUND"


def test_update_resource(client):
    created = client.post("/resources", json=resource_body()).json()
    res = client.put(f"/resources/{created['id']}", json=resource_body(name="작업대 B"))
    assert res.status_code == 200
    assert res.json()["name"] == "작업대 B"


def test_missing_field_is_invalid_input(client):
    body = resource_body()
    del body["name"]
    res = client.post("/resources", json=body)
    assert res.status_code == 400
    assert res.json() == {
        "error": {"code": "INVALID_INPUT", "message": "입력 형식이 올바르지 않습니다."}
    }
