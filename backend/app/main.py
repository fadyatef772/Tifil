"""Application entry point.

Run:  uvicorn app.main:app --reload --port 8000
Docs: http://localhost:8000/docs
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.auth import router as auth_router
from app.api.routes import router
from app.core.config import settings
from app.core.database import Base, engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create tables on startup if they don't exist. Seeding is a separate
    # explicit step (python -m app.seed) so we never clobber real data.
    Base.metadata.create_all(engine)
    yield


app = FastAPI(title=settings.app_name, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(router)


@app.get("/api/health")
def health():
    return {"status": "ok"}
