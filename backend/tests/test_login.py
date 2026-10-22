from datetime import timedelta

import pytest
from conftest import FIXED_NOW
from pwdlib import PasswordHash
from pwdlib.hashers.argon2 import Argon2Hasher

from app import config
from app.services import accounts, sessions
from app.storage import db
from app.validation import reservation_rules

# 로그인·로그아웃·내 계정 (API-SPEC-CHANGE 2.2~2.4, D-049, D-053, D-054, D-062)
PASSWORD = "guest-pass-1"


def signup(client, email="guest@example.com", role="customer", **extra):
    body = {"email": email, "password": PASSWORD, "role": role, "name": "홍길동", **extra}
    assert client.post("/auth/signup", json=body).status_code == 201


def login(client, email="guest@example.com", password=PASSWORD):
    return client.post("/auth/login", json={"email": email, "password": password})


def set_now(monkeypatch, when):
    monkeypatch.setattr(reservation_rules, "now_seoul", lambda: when)


def query(sql, *args):
    conn = db.connect()
    try:
        return conn.execute(sql, args).fetchall()
    finally:
        conn.close()


def test_login_sets_http_only_cookie(client):
    signup(client)
    res = login(client, "  GUEST@example.com ")
    assert res.status_code == 200
    assert res.json() == {"account": {
        "email": "guest@example.com", "name": "홍길동", "role": "customer",
        "operator_status": None, "booking_slug": None,
    }}
    cookie = res.headers["set-cookie"]
    assert cookie.startswith(f"{sessions.COOKIE_NAME}=")
    assert "HttpOnly" in cookie and "SameSite=lax" in cookie and "Max-Age=604800" in cookie
    # 토큰은 본문에 담지 않는다.
    token = res.cookies[sessions.COOKIE_NAME]
    assert token not in res.text


def test_session_is_stored_as_hmac(client):
    signup(client)
    token = login(client).cookies[sessions.COOKIE_NAME]
    rows = query("SELECT token_hash, expires_at FROM sessions")
    assert len(rows) == 1
    assert rows[0]["token_hash"] == sessions.token_hash(token) != token
    assert rows[0]["expires_at"] == (FIXED_NOW + timedelta(days=7)).isoformat()


def test_me_with_and_without_session(client):
    assert client.get("/auth/me").status_code == 401
    signup(client)
    login(client)
    res = client.get("/auth/me")
    assert res.status_code == 200
    assert res.json()["account"]["email"] == "guest@example.com"


def test_wrong_password_and_unknown_email_look_the_same(client):
    signup(client)
    wrong = login(client, password="wrong-pass-1")
    unknown = login(client, email="nobody@example.com")
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json() == unknown.json()
    assert wrong.json()["error"]["code"] == "UNAUTHENTICATED"
    assert "set-cookie" not in wrong.headers


@pytest.mark.parametrize("email", ["guest@example.com", "nobody@example.com"])
def test_five_failures_lock_for_ten_minutes(client, monkeypatch, email):
    signup(client)
    for _ in range(5):
        assert login(client, email, "wrong-pass-1").status_code == 401
    # 잠긴 동안에는 비밀번호가 맞아도 거부한다. 없는 이메일도 똑같이 잠긴다.
    res = login(client, email)
    assert res.status_code == 429
    assert res.json()["error"]["code"] == "TOO_MANY_ATTEMPTS"

    set_now(monkeypatch, FIXED_NOW + timedelta(minutes=10, seconds=1))
    if email == "guest@example.com":
        assert login(client, email).status_code == 200
        assert query("SELECT * FROM login_failures") == []
    else:
        # 잠금이 풀린 뒤의 실패는 1번부터 다시 센다.
        assert login(client, email, "wrong-pass-1").status_code == 401
        assert query("SELECT failed_count FROM login_failures")[0]["failed_count"] == 1


def test_success_resets_failure_count(client):
    signup(client)
    for _ in range(4):
        login(client, password="wrong-pass-1")
    assert login(client).status_code == 200
    assert query("SELECT * FROM login_failures") == []


def test_pending_operator_can_log_in(client):
    signup(client, "owner@example.com", "operator", booking_slug="kim-studio")
    res = login(client, "owner@example.com")
    assert res.status_code == 200
    assert res.json()["account"]["operator_status"] == "pending"


def test_suspended_operator_is_refused_only_with_right_password(client):
    signup(client, "owner@example.com", "operator", booking_slug="kim-studio")
    conn = db.connect()
    conn.execute("UPDATE accounts SET operator_status = 'suspended'")
    conn.close()
    assert login(client, "owner@example.com", "wrong-pass-1").status_code == 401
    res = login(client, "owner@example.com")
    assert res.status_code == 403
    assert res.json()["error"]["code"] == "OPERATOR_SUSPENDED"
    assert query("SELECT * FROM sessions") == []


def test_logout_deletes_session(client):
    signup(client)
    login(client)
    res = client.post("/auth/logout", json={})
    assert res.status_code == 204
    assert query("SELECT * FROM sessions") == []
    assert client.get("/auth/me").status_code == 401
    # 세션이 없어도 같다.
    assert client.post("/auth/logout", json={}).status_code == 204


def test_expired_session_is_deleted(client, monkeypatch):
    signup(client)
    login(client)
    set_now(monkeypatch, FIXED_NOW + timedelta(days=7))
    assert client.get("/auth/me").status_code == 401
    assert query("SELECT * FROM sessions") == []


def test_weak_hash_is_upgraded_on_login(client):
    signup(client)
    weak = PasswordHash((Argon2Hasher(time_cost=1, memory_cost=8192),)).hash(PASSWORD)
    conn = db.connect()
    conn.execute("UPDATE accounts SET password_hash = ?", (weak,))
    conn.close()
    assert login(client).status_code == 200
    stored = query("SELECT password_hash FROM accounts")[0]["password_hash"]
    assert stored != weak and accounts.PASSWORDS.verify(PASSWORD, stored)


def test_non_json_post_is_rejected(client):
    res = client.post("/auth/logout", content=b"", headers={"content-type": "text/plain"})
    assert res.status_code == 400
    assert res.json()["error"]["code"] == "INVALID_INPUT"


def test_missing_or_short_secret_stops_start(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "ENV_FILE", tmp_path / "none.env")
    for value in (None, "short"):
        if value is None:
            monkeypatch.delenv(config.SECRET_NAME, raising=False)
        else:
            monkeypatch.setenv(config.SECRET_NAME, value)
        with pytest.raises(RuntimeError) as exc:
            config.session_secret()
        assert config.SECRET_NAME in str(exc.value)
        if value:
            assert value not in str(exc.value)
