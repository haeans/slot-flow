import os
from pathlib import Path

from dotenv import dotenv_values

# 세션 비밀값은 backend/.env 에만 둔다. Git 에 넣지 않고, 응답·로그·오류 메시지에 담지 않는다. (D-049)
ENV_FILE = Path(__file__).resolve().parents[1] / ".env"
SECRET_NAME = "SLOTFLOW_SESSION_SECRET"
# HMAC-SHA256 키 길이. secrets.token_hex(32)가 만드는 64자 (DATA-MIGRATION-PLAN 6절)
MIN_SECRET_LENGTH = 64


def session_secret() -> bytes:
    """환경 변수가 있으면 그것을, 없으면 backend/.env 를 읽는다. 없거나 짧으면 서버가 시작하지 않는다."""
    value = os.environ.get(SECRET_NAME) or dotenv_values(ENV_FILE).get(SECRET_NAME) or ""
    if len(value) < MIN_SECRET_LENGTH:
        # 값은 출력하지 않고 항목 이름만 알린다.
        raise RuntimeError(
            f"{SECRET_NAME} 가 없거나 {MIN_SECRET_LENGTH}자보다 짧습니다. backend/.env 를 확인하세요."
        )
    return value.encode()
