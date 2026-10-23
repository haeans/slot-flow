import sqlite3

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


class ApiError(Exception):
    """거부·실패 응답 하나. 형식은 { "error": { "code", "message" } } 이다. (D-006)"""

    def __init__(self, status: int, code: str, message: str):
        super().__init__(code)
        self.status = status
        self.code = code
        self.message = message


def invalid_input(message: str = "입력 형식이 올바르지 않습니다.") -> ApiError:
    return ApiError(400, "INVALID_INPUT", message)


def resource_not_found() -> ApiError:
    return ApiError(404, "RESOURCE_NOT_FOUND", "존재하지 않는 자원입니다.")


def storage_error() -> ApiError:
    return ApiError(500, "STORAGE_ERROR", "저장소 오류로 요청을 처리하지 못했습니다.")


def error_response(error: ApiError) -> JSONResponse:
    return JSONResponse(
        status_code=error.status,
        content={"error": {"code": error.code, "message": error.message}},
    )


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def handle_api_error(request: Request, exc: ApiError):
        return error_response(exc)

    # FastAPI 기본 422도 같은 형식의 INVALID_INPUT(400)으로 바꾼다. (D-026)
    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(request: Request, exc: RequestValidationError):
        return error_response(invalid_input())

    # 저장소 CHECK에 걸리는 등 판정이 빠진 경우는 STORAGE_ERROR(500)다. (D-036)
    @app.exception_handler(sqlite3.Error)
    async def handle_storage_error(request: Request, exc: sqlite3.Error):
        return error_response(storage_error())
