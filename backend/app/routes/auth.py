from fastapi import APIRouter, Request, Response

from app.services import accounts, sessions
from app.storage.db import connect
from app.validation.account_input import LoginInput, SignupInput, check_signup_input, normalize_email

router = APIRouter(prefix="/auth")


@router.post("/signup", status_code=201)
def signup(data: SignupInput):
    """운영자(승인 대기) 또는 회원 고객 계정을 만든다. 세션은 만들지 않는다. (API-SPEC-CHANGE 2.1)"""
    email, name = check_signup_input(data)
    # argon2 계산은 느리므로 쓰기 단위 밖에서 한다.
    password_hash = accounts.hash_password(data.password)
    conn = connect()
    try:
        account = accounts.create_account(
            conn, email=email, password_hash=password_hash, name=name,
            role=data.role, booking_slug=data.booking_slug,
        )
    finally:
        conn.close()
    return {"account": account}


@router.post("/login")
def login(data: LoginInput, response: Response):
    """토큰은 HttpOnly 쿠키에만 담고 본문에는 담지 않는다. (API-SPEC-CHANGE 2.2, D-049)"""
    email = normalize_email(data.email)
    conn = connect()
    try:
        account, token = sessions.login(conn, email, data.password)
    finally:
        conn.close()
    # Secure 는 배포 때 켠다. 지금은 http://localhost 로만 쓴다. (D-049)
    response.set_cookie(
        sessions.COOKIE_NAME, token, max_age=sessions.SESSION_DAYS * 24 * 60 * 60,
        path="/", httponly=True, samesite="lax", secure=False,
    )
    return {"account": account}


@router.post("/logout", status_code=204)
def logout(request: Request, response: Response):
    """세션이 없어도 거부하지 않는다. 쿠키는 항상 비운다. (API-SPEC-CHANGE 2.3)"""
    response.delete_cookie(sessions.COOKIE_NAME, path="/")
    conn = connect()
    try:
        sessions.logout(conn, request.cookies.get(sessions.COOKIE_NAME))
    finally:
        conn.close()


@router.get("/me")
def me(request: Request):
    conn = connect()
    try:
        row = sessions.find_account(conn, request.cookies.get(sessions.COOKIE_NAME))
    finally:
        conn.close()
    if row is None:
        raise sessions.unauthenticated()
    return {"account": accounts.account_object(row)}
