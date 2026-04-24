from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status

from src.arkana_api_service.dependencies import get_current_user, get_user_manager
from src.arkana_api_service.route_auth import require_route_auth
from src.arkana_api_service.routes.help_utils import build_help, with_help
from src.arkana_auth.user_manager import UserManager
from src.arkana_auth.user_object import ArkanaUser
from src.arkana_mdd_db.main_db import AuthUser

router = APIRouter(tags=["user"])


def _require_admin_or_root(current_user: ArkanaUser) -> None:
    if current_user.user_role not in {"root", "admin"}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin or root role required")


def _resolve_user_by_id(current_user: ArkanaUser, user_id: str) -> AuthUser:
    query = """
        SELECT user_id, user_name, user_role, user_storage_db_id, supabase_user_id, supabase_email
        FROM arkana_user
        WHERE user_id = %s
        LIMIT 1
    """
    row = current_user.main_db._fetchone(query, (user_id,))
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return AuthUser(
        user_id=str(row[0]),
        user_name=str(row[1]),
        user_role=str(row[2]),
        user_storage_db_id=int(row[3]) if row[3] is not None else None,
        supabase_user_id=str(row[4]) if row[4] is not None else None,
        supabase_email=str(row[5]) if row[5] is not None else None,
    )


@router.get("/user/login_check")
def get_user_login_check(
    current_user: ArkanaUser = Depends(get_current_user),
    help: bool = Query(default=False),
) -> dict[str, object]:
    require_route_auth(current_user, "get_user_login_check")
    return with_help(
        {
            "can_login": True,
            "user_id": current_user.user_id,
            "user_name": current_user.user_name,
            "user_role": current_user.user_role,
        },
        help_enabled=help,
        help_payload=build_help(
            endpoint="/user/login_check",
            method="GET",
            description="Validates the provided basic auth credentials and returns the resolved user identity.",
            query_parameters={"help": "Optional. If true, appends endpoint documentation to the response."},
            returns="JSON object with login status, user_id, user_name and user_role.",
        ),
    )


@router.get("/user/usage")
def get_user_usage(
    current_user: ArkanaUser = Depends(get_current_user),
    help: bool = Query(default=False),
) -> dict[str, object]:
    require_route_auth(current_user, "get_user_usage")
    accounting = current_user.get_accounting_obj().load_by_db()
    usage = accounting.get_today_usage()
    return with_help(
        {
            "user_id": current_user.user_id,
            "service": accounting.service,
            **usage,
        },
        help_enabled=help,
        help_payload=build_help(
            endpoint="/user/usage",
            method="GET",
            description="Returns today's runtime usage for the authenticated user.",
            query_parameters={"help": "Optional. If true, appends endpoint documentation to the response."},
            returns="JSON object with today's usage counters.",
        ),
    )


@router.get("/user/max_usage")
def get_user_max_usage(
    current_user: ArkanaUser = Depends(get_current_user),
    help: bool = Query(default=False),
) -> dict[str, object]:
    require_route_auth(current_user, "get_user_max_usage")
    accounting = current_user.get_accounting_obj().load_by_db()
    if current_user.user_role == "root":
        max_usage = {"runtime_seconds_max": -1, "tokens_max": -1}
    else:
        max_usage = accounting.get_daily_max_usage()
    return with_help(
        {
            "user_id": current_user.user_id,
            "service": accounting.service,
            **max_usage,
        },
        help_enabled=help,
        help_payload=build_help(
            endpoint="/user/max_usage",
            method="GET",
            description="Returns the daily runtime/token limit for the authenticated user. Root or unlimited users get -1.",
            query_parameters={"help": "Optional. If true, appends endpoint documentation to the response."},
            returns="JSON object with daily usage limits.",
        ),
    )


@router.get("/user/{user_id}/usage")
def get_specific_user_usage(
    user_id: str,
    current_user: ArkanaUser = Depends(get_current_user),
    help: bool = Query(default=False),
) -> dict[str, object]:
    require_route_auth(current_user, "get_specific_user_usage")
    _require_admin_or_root(current_user)
    auth_user = _resolve_user_by_id(current_user, user_id)

    accounting = current_user.get_accounting_obj().__class__(
        auth_user.user_id,
        main_db=current_user.main_db,
    ).load_by_db()
    usage = accounting.get_today_usage()
    return with_help(
        {
            "user_id": auth_user.user_id,
            "service": accounting.service,
            **usage,
        },
        help_enabled=help,
        help_payload=build_help(
            endpoint="/user/{user_id}/usage",
            method="GET",
            description="Admin/root endpoint returning today's runtime usage for a specific user.",
            path_parameters={"user_id": "The target user id."},
            query_parameters={"help": "Optional. If true, appends endpoint documentation to the response."},
            returns="JSON object with today's usage counters for the requested user.",
        ),
    )


@router.post("/user/{user_id}/reload")
def reload_specific_user(
    user_id: str,
    current_user: ArkanaUser = Depends(get_current_user),
    user_manager: UserManager = Depends(get_user_manager),
    help: bool = Query(default=False),
) -> dict[str, object]:
    require_route_auth(current_user, "reload_specific_user")
    _require_admin_or_root(current_user)
    auth_user = _resolve_user_by_id(current_user, user_id)
    removed_entries = user_manager.reload_user_buffer(auth_user.user_id)
    if current_user.user_id == auth_user.user_id:
        current_user.invalidate_buffer()
    return with_help(
        {
            "status": "ok",
            "user_id": auth_user.user_id,
            "removed_cache_entries": removed_entries,
        },
        help_enabled=help,
        help_payload=build_help(
            endpoint="/user/{user_id}/reload",
            method="POST",
            description="Admin/root endpoint that invalidates all cached user buffers for the requested user.",
            path_parameters={"user_id": "The target user id."},
            query_parameters={"help": "Optional. If true, appends endpoint documentation to the response."},
            returns="JSON object with the invalidated user id and number of removed cache entries.",
        ),
    )


@router.post("/user/reload")
def reload_current_user(
    current_user: ArkanaUser = Depends(get_current_user),
    user_manager: UserManager = Depends(get_user_manager),
    help: bool = Query(default=False),
) -> dict[str, object]:
    require_route_auth(current_user, "reload_current_user")
    removed_entries = user_manager.reload_user_buffer(current_user.user_id)
    current_user.invalidate_buffer()
    return with_help(
        {
            "status": "ok",
            "user_id": current_user.user_id,
            "removed_cache_entries": removed_entries,
        },
        help_enabled=help,
        help_payload=build_help(
            endpoint="/user/reload",
            method="POST",
            description="Invalidates all cached buffers for the authenticated user.",
            query_parameters={"help": "Optional. If true, appends endpoint documentation to the response."},
            returns="JSON object with the invalidated user id and number of removed cache entries.",
        ),
    )
