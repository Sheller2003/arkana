from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from src.arkana_api_service.dependencies import get_current_user
from src.arkana_auth.user_object import ArkanaUser

router = APIRouter(tags=["user"])


@router.get("/user/usage")
def get_user_usage(
    current_user: ArkanaUser = Depends(get_current_user),
) -> dict[str, object]:
    accounting = current_user.get_accounting_obj().load_by_db()
    usage = accounting.get_today_usage()
    return {
        "user_id": current_user.user_id,
        "service": accounting.service,
        **usage,
    }


@router.get("/user/max_usage")
def get_user_max_usage(
    current_user: ArkanaUser = Depends(get_current_user),
) -> dict[str, object]:
    accounting = current_user.get_accounting_obj().load_by_db()
    if current_user.user_role == "root":
        max_usage = {"runtime_seconds_max": -1, "tokens_max": -1}
    else:
        max_usage = accounting.get_daily_max_usage()
    return {
        "user_id": current_user.user_id,
        "service": accounting.service,
        **max_usage,
    }


@router.get("/user/usage/{user_id}")
def get_specific_user_usage(
    user_id: str,
    current_user: ArkanaUser = Depends(get_current_user),
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
    return {
        "user_id": auth_user.user_id,
        "service": accounting.service,
        **usage,
    }
