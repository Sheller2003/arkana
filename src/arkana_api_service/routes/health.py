from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from src.arkana_auth.user_object import ArkanaUser
from src.arkana_api_service.dependencies import get_current_user
from src.arkana_api_service.routes.help_utils import build_help, with_help

router = APIRouter(tags=["health"])


@router.get("/health")
def health(
    _: ArkanaUser = Depends(get_current_user),
    help: bool = Query(default=False),
) -> dict[str, object]:
    return with_help(
        {"status": "ok"},
        help_enabled=help,
        help_payload=build_help(
            endpoint="/health",
            method="GET",
            description="Returns the API health status.",
            query_parameters={"help": "Optional. If true, appends endpoint documentation to the response."},
            returns="JSON object with the current health status.",
        ),
    )
