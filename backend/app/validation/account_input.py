import re

from pydantic import BaseModel, StrictStr

from app.errors import invalid_input

ROLES_FOR_SIGNUP = ("operator", "customer")

# 영문 소문자·숫자·-, 3~30자, -로 시작하거나 끝나지 않음 (D-059)
_SLUG = re.compile(r"^[a-z0-9][a-z0-9-]{1,28}[a-z0-9]$")


class SignupInput(BaseModel):
    email: StrictStr
    password: StrictStr
    role: StrictStr
    name: StrictStr
    booking_slug: StrictStr | None = None


class LoginInput(BaseModel):
    email: StrictStr
    password: StrictStr


def normalize_email(value: str) -> str:
    """앞뒤 공백을 지우고 소문자로 바꾼다. 3~254자, @ 하나, 앞뒤가 비지 않고 공백이 없어야 한다. (D-056)"""
    email = value.strip().lower()
    if not 3 <= len(email) <= 254 or email.count("@") != 1 or any(c.isspace() for c in email):
        raise invalid_input("이메일 형식이 올바르지 않습니다.")
    local, domain = email.split("@")
    if not local or not domain:
        raise invalid_input("이메일 형식이 올바르지 않습니다.")
    return email


def check_password(value: str) -> None:
    """8~128자. 앞뒤 공백을 지우지 않는다. (D-059)"""
    if not 8 <= len(value) <= 128:
        raise invalid_input("비밀번호는 8~128자여야 합니다.")


def normalize_name(value: str) -> str:
    name = value.strip()
    if not 1 <= len(name) <= 50:
        raise invalid_input("이름은 1~50자여야 합니다.")
    return name


def check_booking_slug(value: str) -> None:
    # 대문자는 소문자로 바꾸지 않고 거부한다. (API-SPEC-CHANGE 2.1)
    if not _SLUG.match(value):
        raise invalid_input("예약 주소명은 영문 소문자·숫자·-로 된 3~30자이고, -로 시작하거나 끝날 수 없습니다.")


def check_signup_input(data: SignupInput) -> tuple[str, str]:
    """가입 입력 형식 검사. 정리한 이메일과 이름을 돌려준다. (API-SPEC-CHANGE 2.1)"""
    if data.role not in ROLES_FOR_SIGNUP:
        raise invalid_input("가입할 수 있는 역할은 operator, customer 뿐입니다.")
    email = normalize_email(data.email)
    check_password(data.password)
    name = normalize_name(data.name)
    if data.role == "operator":
        if data.booking_slug is None:
            raise invalid_input("운영자는 예약 주소명이 필요합니다.")
        check_booking_slug(data.booking_slug)
    elif data.booking_slug is not None:
        raise invalid_input("고객은 예약 주소명을 보내지 않습니다.")
    return email, name
