"""관리자 계정을 한 번 만든다. 가입 화면은 없다. (D-042, D-050)

실행: backend 에서 `uv run python -m app.create_admin`
비밀번호는 실행할 때 입력받고 파일에 남기지 않는다.
"""
import sys
from getpass import getpass

from app.errors import ApiError
from app.services import accounts
from app.storage.db import connect, init_db
from app.validation.account_input import check_password, normalize_email, normalize_name


def create_admin(email: str, name: str, password: str) -> dict:
    email = normalize_email(email)
    name = normalize_name(name)
    check_password(password)
    init_db()
    conn = connect()
    try:
        # 관리자는 1명이다. 저장소의 부분 유일 인덱스가 최종 보장이다. (D-050)
        if accounts.admin_exists(conn):
            raise ApiError(409, "ADMIN_EXISTS", "관리자 계정이 이미 있습니다.")
        return accounts.create_account(
            conn, email=email, password_hash=accounts.hash_password(password), name=name, role="admin"
        )
    finally:
        conn.close()


def main() -> None:
    email = input("관리자 이메일: ")
    name = input("이름: ")
    password = getpass("비밀번호: ")
    if getpass("비밀번호 확인: ") != password:
        sys.exit("비밀번호가 서로 다릅니다.")
    try:
        account = create_admin(email, name, password)
    except ApiError as exc:
        sys.exit(exc.message)
    print(f"관리자 계정을 만들었습니다: {account['email']}")


if __name__ == "__main__":
    main()
