from .dashboard import router as dashboard_router
from .db import router as db_router
from .frames import router as frames_router
from .groups import router as groups_router
from .health import router as health_router
from .user import router as user_router

__all__ = ["dashboard_router", "db_router", "frames_router", "groups_router", "health_router", "user_router"]
