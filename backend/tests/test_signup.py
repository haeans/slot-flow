import pytest

from app.services import accounts
from app.storage import db

# POST /auth/signup (API-SPEC-CHANGE 2.1)


def operator_body(**overrides):
    body = {"email": "Owner@Example.com", "password": "owner-pass-1", "role": "operator",
            "name": " 김공방 ", "booking_slug": "kim-studio"}
    body.update(overrides)
    return body


def customer_body(**overrides):
    body = {"email": "guest@example.com", "password": "guest-pass-1", "role": "customer",
            "name": "홍길동"}
    body.update(overrides)
    return body


def test_operator_signup_is_pending(client):
    res = client.post("/auth/signup", json=operator_body())
    assert res.status_code == 201
    assert res.json() == {"account": {
        "email": "owner@example.com", "name": "김공방", "role": "operator",
        "operator_status": "pending", "booking_slug": "kim-studio",
    }}
    # 세션은 만들지 않는다.
    assert "set-cookie" not in res.headers


def test_customer_signup(client):
    res = client.post("/auth/signup", json=customer_body())
    assert res.status_code == 201
    assert res.json()["account"]["role"] == "customer"
    assert res.json()["account"]["operator_status"] is None


def test_password_is_stored_as_argon2id(client):
    client.post("/auth/signup", json=customer_body())
    conn = db.connect()
    row = accounts.find_by_email(conn, "guest@example.com")
    conn.close()
    assert row["password_hash"].startswith("$argon2id$")
    assert "guest-pass-1" not in row["password_hash"]


def test_response_has_no_secret_fields(client):
    account = client.post("/auth/signup", json=customer_body()).json()["account"]
    assert set(account) == {"email", "name", "role", "operator_status", "booking_slug"}


@pytest.mark.parametrize(
    "body",
    [
        operator_body(role="admin"),
        operator_body(role="owner"),
        operator_body(booking_slug=None),
        operator_body(booking_slug="Kim-Studio"),
        operator_body(booking_slug="kim_studio"),
        operator_body(booking_slug="-kim"),
        operator_body(booking_slug="ab"),
        customer_body(booking_slug="guest-slug"),
        customer_body(email="no-at-sign"),
        customer_body(email="a@b@c"),
        customer_body(email="a b@example.com"),
        customer_body(password="short"),
        customer_body(password="x" * 129),
        customer_body(name="   "),
        customer_body(name="가" * 51),
        {"email": "guest@example.com", "password": "guest-pass-1", "role": "customer"},
    ],
)
def test_invalid_signup_is_rejected(client, body):
    res = client.post("/auth/signup", json=body)
    assert res.status_code == 400
    assert res.json()["error"]["code"] == "INVALID_INPUT"


def test_duplicate_email_is_rejected(client):
    client.post("/auth/signup", json=customer_body())
    res = client.post("/auth/signup", json=operator_body(email="GUEST@example.com"))
    assert res.status_code == 409
    assert res.json()["error"]["code"] == "EMAIL_TAKEN"


def test_duplicate_booking_slug_is_rejected(client):
    client.post("/auth/signup", json=operator_body())
    res = client.post("/auth/signup", json=operator_body(email="other@example.com"))
    assert res.status_code == 409
    assert res.json()["error"]["code"] == "BOOKING_SLUG_TAKEN"
