from fastapi import APIRouter

from app.services import accounts
from app.storage.db import connect
from app.validation.account_input import SignupInput, check_signup_input

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
