from __future__ import annotations

from fastapi import FastAPI

from src.arkana_api_service.routes import dashboard_router, db_router, frames_router, health_router


def create_app() -> FastAPI:
    app = FastAPI(title="arkanaMDD API", version="0.1.0")
    app.include_router(health_router)
    app.include_router(dashboard_router)
    app.include_router(db_router)
    app.include_router(frames_router)
    return app


app = create_app()
