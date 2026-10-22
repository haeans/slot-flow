"""비밀번호를 잊은 계정의 비밀번호를 관리자가 새로 정한다. 외부 알림이 없기 때문이다. (D-059, F-05)

실행: backend 에서 `uv run python -m app.reset_password`
그 계정의 세션과 로그인 실패 기록을 지운다.
"""
import sys
from getpass import getpass

from app.errors import ApiError
from app.services import accounts
from app.storage.db import connect, init_db
from app.validation.account_input import check_password, normalize_email


def reset_password(email: str, password: str) -> bool:
    email = normalize_email(email)
    check_password(password)
    init_db()
    conn = connect()
    try:
        return accounts.set_password(conn, email, accounts.hash_password(password))
    finally:
        conn.close()


def main() -> None:
    email = input("계정 이메일: ")
    password = getpass("새 비밀번호: ")
    if getpass("새 비밀번호 확인: ") != password:
        sys.exit("비밀번호가 서로 다릅니다.")
    try:
        changed = reset_password(email, password)
    except ApiError as exc:
        sys.exit(exc.message)
    if not changed:
        sys.exit("그 이메일의 계정이 없습니다.")
    print(f"비밀번호를 바꿨습니다: {email.strip().lower()}")


if __name__ == "__main__":
    main()
