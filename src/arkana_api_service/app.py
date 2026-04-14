from __future__ import annotations

from fastapi import FastAPI

from src.arkana_api_service.routes import (
    db_router,
    frames_router,
    groups_router,
    health_router,
    report_router,
    user_router,
)


def create_app() -> FastAPI:
    app = FastAPI(title="arkanaMDD API", version="0.1.0")
    app.include_router(health_router)
    app.include_router(user_router)
    app.include_router(groups_router)
    app.include_router(report_router)
    app.include_router(db_router)
    app.include_router(frames_router)
    return app


app = create_app()
