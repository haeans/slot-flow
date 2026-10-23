from contextlib import asynccontextmanager

from fastapi import FastAPI, Request

from app import config
from app.errors import error_response, install_error_handlers, invalid_input
from app.routes import admin, auth, me, reservations, resources
from app.storage.db import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 세션 비밀값이 없으면 서버가 시작하지 않는다. (D-049)
    config.session_secret()
    init_db()
    yield


app = FastAPI(title="slot-flow", lifespan=lifespan)
install_error_handlers(app)
app.include_router(resources.router)
app.include_router(reservations.router)
app.include_router(auth.router)
app.include_router(admin.router)
app.include_router(me.router)


@app.middleware("http")
async def json_only(request: Request, call_next):
    # 상태를 바꾸는 요청은 JSON 만 받는다. SameSite=Lax 쿠키와 함께 CSRF 를 막는다. (API-SPEC-CHANGE 5절)
    if request.method in ("POST", "PUT", "PATCH", "DELETE"):
        content_type = request.headers.get("content-type", "")
        if not content_type.startswith("application/json"):
            return error_response(invalid_input("요청은 JSON(application/json)이어야 합니다."))
    return await call_next(request)


@app.get("/health")
def health():
    return {"status": "ok"}
