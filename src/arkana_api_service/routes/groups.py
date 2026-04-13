from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status

from src.arkana_api_service.dependencies import get_current_user
from src.arkana_api_service.routes.help_utils import build_help, with_help
from src.arkana_auth.amezitUserObject import AmezitUserObject
from src.arkana_auth.amezit_supabase_service import AmezitSupabaseService, SupabaseClientError
from src.arkana_auth.user_object import ArkanaUser
from src.arkana_mdd_db.models import AssignGroupRequest, CreateGroupRequest

router = APIRouter(tags=["groups"])


def _require_supabase_user(current_user: ArkanaUser) -> AmezitUserObject:
    if not isinstance(current_user, AmezitUserObject):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Supabase login required",
        )
    if not current_user.supabase_access_token:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Supabase access token required",
        )
    return current_user


def _get_supabase_service() -> AmezitSupabaseService:
    return AmezitSupabaseService.from_env()


@router.post("/groups/create_group")
def create_group(
    request: CreateGroupRequest,
    current_user: ArkanaUser = Depends(get_current_user),
    help: bool = Query(default=False),
) -> dict[str, object]:
    supabase_user = _require_supabase_user(current_user)
    service = _get_supabase_service()
    try:
        group_id = service.create_group(
            group_name=request.group_name,
            access_token=supabase_user.supabase_access_token,
        )
    except SupabaseClientError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return with_help(
        {"group_id": group_id},
        help_enabled=help,
        help_payload=build_help(
            endpoint="/groups/create_group",
            method="POST",
            description="Creates a Supabase group and returns its id.",
            query_parameters={"help": "Optional. If true, appends endpoint documentation to the response."},
            body="CreateGroupRequest JSON body.",
            returns="JSON object containing the created group_id.",
        ),
    )


@router.get("/groups/{group_id}/members")
def get_group_members(
    group_id: int,
    current_user: ArkanaUser = Depends(get_current_user),
    help: bool = Query(default=False),
) -> dict[str, object]:
    supabase_user = _require_supabase_user(current_user)
    service = _get_supabase_service()
    try:
        members = service.get_group_members(
            group_id=group_id,
            access_token=supabase_user.supabase_access_token,
        )
    except SupabaseClientError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return with_help(
        {"group_id": group_id, "members": members},
        help_enabled=help,
        help_payload=build_help(
            endpoint="/groups/{group_id}/members",
            method="GET",
            description="Returns the member ids for a Supabase group.",
            path_parameters={"group_id": "The target group id."},
            query_parameters={"help": "Optional. If true, appends endpoint documentation to the response."},
            returns="JSON object with the group id and member list.",
        ),
    )


@router.delete("/groups/{group_id}")
def delete_group(
    group_id: int,
    current_user: ArkanaUser = Depends(get_current_user),
    help: bool = Query(default=False),
) -> dict[str, object]:
    supabase_user = _require_supabase_user(current_user)
    service = _get_supabase_service()
    try:
        service.delete_group(
            group_id=group_id,
            access_token=supabase_user.supabase_access_token,
        )
    except SupabaseClientError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return with_help(
        {"status": "ok", "group_id": group_id},
        help_enabled=help,
        help_payload=build_help(
            endpoint="/groups/{group_id}",
            method="DELETE",
            description="Deletes a Supabase group.",
            path_parameters={"group_id": "The target group id."},
            query_parameters={"help": "Optional. If true, appends endpoint documentation to the response."},
            returns="JSON object containing the deleted group id.",
        ),
    )


@router.post("/groups/{group_id}/assign")
def assign_group(
    group_id: int,
    request: AssignGroupRequest,
    current_user: ArkanaUser = Depends(get_current_user),
    help: bool = Query(default=False),
) -> dict[str, object]:
    supabase_user = _require_supabase_user(current_user)
    service = _get_supabase_service()
    try:
        service.assign_to_group(
            user_id=request.user_id,
            group_id=group_id,
            access_token=supabase_user.supabase_access_token,
        )
    except SupabaseClientError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return with_help(
        {"status": "ok", "group_id": group_id, "user_id": request.user_id},
        help_enabled=help,
        help_payload=build_help(
            endpoint="/groups/{group_id}/assign",
            method="POST",
            description="Assigns a user to a Supabase group.",
            path_parameters={"group_id": "The target group id."},
            query_parameters={"help": "Optional. If true, appends endpoint documentation to the response."},
            body="AssignGroupRequest JSON body.",
            returns="JSON object confirming the assignment.",
        ),
    )
