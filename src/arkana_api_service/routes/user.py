from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status

from src.arkana_api_service.dependencies import get_current_user
from src.arkana_api_service.routes.help_utils import build_help, with_help
from src.arkana_auth.user_object import ArkanaUser

router = APIRouter(tags=["user"])


@router.get("/user/login_check")
def get_user_login_check(
    current_user: ArkanaUser = Depends(get_current_user),
    help: bool = Query(default=False),
) -> dict[str, object]:
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


@router.get("/user/usage/{user_id}")
def get_specific_user_usage(
    user_id: str,
    current_user: ArkanaUser = Depends(get_current_user),
    help: bool = Query(default=False),
) -> dict[str, object]:
    if current_user.user_role != "root":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Root role required")

    auth_user = current_user.main_db.get_user_by_name(user_id)
    if auth_user is None:
        query = """
            SELECT user_id, user_name, user_role, user_storage_db_id
            FROM arkana_user
            WHERE user_id = %s
            LIMIT 1
        """
        row = current_user.main_db._fetchone(query, (user_id,))
        if row is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
        from src.arkana_mdd_db.main_db import AuthUser

        auth_user = AuthUser(
            user_id=str(row[0]),
            user_name=str(row[1]),
            user_role=str(row[2]),
            user_storage_db_id=int(row[3]) if row[3] is not None else None,
        )

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
            endpoint="/user/usage/{user_id}",
            method="GET",
            description="Root-only endpoint returning today's runtime usage for a specific user.",
            path_parameters={"user_id": "The target user id."},
            query_parameters={"help": "Optional. If true, appends endpoint documentation to the response."},
            returns="JSON object with today's usage counters for the requested user.",
        ),
    )
