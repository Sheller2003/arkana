from __future__ import annotations

from fastapi import APIRouter, Depends

from src.arkana_auth.user_object import ArkanaUser
from src.arkana_api_service.dependencies import get_current_user

router = APIRouter(tags=["health"])


@router.get("/health")
def health(_: ArkanaUser = Depends(get_current_user)) -> dict[str, str]:
    return {"status": "ok"}
