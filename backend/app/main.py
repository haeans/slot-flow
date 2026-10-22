from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.errors import install_error_handlers
from app.routes import auth, reservations, resources
from app.storage.db import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="slot-flow", lifespan=lifespan)
install_error_handlers(app)
app.include_router(resources.router)
app.include_router(reservations.router)
app.include_router(auth.router)


@app.get("/health")
def health():
    return {"status": "ok"}
