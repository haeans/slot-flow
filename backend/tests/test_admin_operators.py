import pytest
from conftest import add_operator, login_as, resource_body

from app.create_admin import create_admin
from app.storage import db

# 운영자 목록·승인·정지 (D-043, D-053, D-067)
ADMIN = ("admin@example.com", "admin-pass-1")


@pytest.fixture
def admin_client(client, anon_client):
    create_admin(ADMIN[0], "관리자", ADMIN[1])
    add_operator(anon_client, "wait@example.com", "wait-studio", status="pending")
    login_as(client, *ADMIN)
    return client


def code_of(res):
    return res.status_code, res.json()["error"]["code"]


def test_list_operators(admin_client):
    res = admin_client.get("/admin/operators")
    assert res.status_code == 200
    assert res.json() == {"operators": [{
        "email": "wait@example.com", "name": "운영자", "role": "operator",
        "operator_status": "pending", "booking_slug": "wait-studio",
    }]}


def test_only_admin_can_manage(client, anon_client):
    assert code_of(anon_client.get("/admin/operators")) == (401, "UNAUTHENTICATED")
    add_operator(client)
    login_as(client, "op@example.com")
    assert code_of(client.get("/admin/operators")) == (403, "FORBIDDEN")
    assert code_of(client.post("/admin/operators/op-studio/approve", json={})) == (403, "FORBIDDEN")


def test_approve_lets_operator_create_resources(admin_client, anon_client):
    res = admin_client.post("/admin/operators/wait-studio/approve", json={})
    assert res.status_code == 200
    assert res.json()["operator"]["operator_status"] == "approved"
    login_as(anon_client, "wait@example.com")
    assert anon_client.post("/resources", json=resource_body()).status_code == 201


def test_suspend_deletes_sessions(admin_client, anon_client):
    admin_client.post("/admin/operators/wait-studio/approve", json={})
    login_as(anon_client, "wait@example.com")
    res = admin_client.post("/admin/operators/wait-studio/suspend", json={})
    assert res.json()["operator"]["operator_status"] == "suspended"
    conn = db.connect()
    assert conn.execute("SELECT count(*) FROM sessions s JOIN accounts a ON a.id = s.account_id"
                        " WHERE a.email = 'wait@example.com'").fetchone()[0] == 0
    conn.close()
    # 세션이 지워져 바로 로그인이 풀린다.
    assert code_of(anon_client.post("/resources", json=resource_body())) == (401, "UNAUTHENTICATED")


def test_suspended_operator_cannot_be_approved_again(admin_client):
    admin_client.post("/admin/operators/wait-studio/suspend", json={})
    res = admin_client.post("/admin/operators/wait-studio/approve", json={})
    assert code_of(res) == (409, "INVALID_OPERATOR_STATE")


def test_unknown_operator(admin_client):
    assert code_of(admin_client.post("/admin/operators/nobody/approve", json={})) == (404, "OPERATOR_NOT_FOUND")
