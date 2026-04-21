from __future__ import annotations

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.arkana_mdd_db.config import load_env

from src.arkana_api_service.routes import (
    db_router,
    frames_router,
    groups_router,
    health_router,
    report_router,
    user_router,
)


def _get_cors_origins() -> tuple[list[str], bool]:
    load_env()
    raw_origins = os.getenv("ARKANA_CORS_ALLOW_ORIGINS", "").strip()
    if not raw_origins:
        return ["*"], True
    origins = [origin.strip() for origin in raw_origins.split(",") if origin.strip()]
    if not origins:
        return ["*"], True
    if "*" in origins:
        return ["*"], True
    return origins, False


def create_app() -> FastAPI:
    app = FastAPI(title="arkanaMDD API", version="0.1.0")
    allow_origins, allow_all_origins = _get_cors_origins()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allow_origins,
        allow_credentials=not allow_all_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(health_router)
    app.include_router(user_router)
    app.include_router(groups_router)
    app.include_router(report_router)
    app.include_router(db_router)
    app.include_router(frames_router)
    return app


app = create_app()
