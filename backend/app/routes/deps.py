import sqlite3

from fastapi import Request

from app.errors import ApiError
from app.services import sessions
from app.storage.db import connect

# 진입 단계의 세션 확인과 역할 검사(C-5). 요청마다 FastAPI 의존성으로 붙인다. (D-005, D-052, API-SPEC-CHANGE 4절)


def session_account(request: Request) -> sqlite3.Row | None:
    """유효한 세션의 계정. 없거나 만료면 None. 고객 요청은 None 이면 비회원으로 처리한다. (D-051)"""
    conn = connect()
    try:
        return sessions.find_account(conn, request.cookies.get(sessions.COOKIE_NAME))
    finally:
        conn.close()


def approved_operator(request: Request) -> sqlite3.Row:
    account = session_account(request)
    if account is None:
        raise sessions.unauthenticated()
    if account["role"] != "operator":
        raise ApiError(403, "FORBIDDEN", "이 기능을 쓸 권한이 없습니다.")
    if account["operator_status"] == "pending":
        raise ApiError(403, "OPERATOR_NOT_APPROVED", "관리자 승인을 기다리고 있습니다.")
    if account["operator_status"] == "suspended":
        raise ApiError(403, "OPERATOR_SUSPENDED", "정지된 운영자 계정입니다. 관리자에게 문의해 주세요.")
    return account


def admin_account(request: Request) -> sqlite3.Row:
    account = session_account(request)
    if account is None:
        raise sessions.unauthenticated()
    if account["role"] != "admin":
        raise ApiError(403, "FORBIDDEN", "이 기능을 쓸 권한이 없습니다.")
    return account
