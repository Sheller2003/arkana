from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status

from src.arkana_auth.user_object import ArkanaUser
from src.arkana_api_service.dependencies import get_current_user, get_main_db
from src.arkana_mdd_db.constants import EXCLUDED_SYSTEM_SCHEMAS, EXCLUDED_SYSTEM_TABLES
from src.arkana_mdd_db.main_db import ArkanaMainDB
from src.arkana_mdd_db.models import (
    CreateDBConnectionRequest,
    CreateDBRequest,
    KeyModelsRequest,
    PasswordStatusResponse,
    PasswordUpdateRequest,
    PersonalUserRequest,
)

router = APIRouter(tags=["db"])


@router.get("/db/{db_id}/")
def get_db(
    db_id: int,
    current_user: ArkanaUser = Depends(get_current_user),
    main_db: ArkanaMainDB = Depends(get_main_db),
) -> dict[str, object]:
    db_record = main_db.get_db_schema(db_id)
    if db_record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Database not found")
    if not current_user.can_access_db(db_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    return db_record.__dict__


@router.get("/db/{db_id}/tables")
def get_db_tables(
    db_id: int,
    current_user: ArkanaUser = Depends(get_current_user),
    main_db: ArkanaMainDB = Depends(get_main_db),
) -> dict[str, object]:
    if not current_user.can_access_db(db_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    tables = main_db.list_tables(db_id)
    visible_tables = [
        table
        for table in tables
        if table["table_name"] not in EXCLUDED_SYSTEM_TABLES
        and table.get("table_schema", "sys") not in EXCLUDED_SYSTEM_SCHEMAS
    ]
    return {"db_id": db_id, "tables": visible_tables}


@router.post("/db/{db_id}/key_models")
def get_key_models(
    db_id: int,
    request: KeyModelsRequest,
    current_user: ArkanaUser = Depends(get_current_user),
    main_db: ArkanaMainDB = Depends(get_main_db),
) -> dict[str, object]:
    if not current_user.can_access_db(db_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    return main_db.build_key_models(
        db_id,
        start_tables=request.start_tables,
        max_distance=request.max_distance,
        include_all=request.include_all,
    )


@router.post("/db/")
def create_db(
    request: CreateDBRequest,
    current_user: ArkanaUser = Depends(get_current_user),
    main_db: ArkanaMainDB = Depends(get_main_db),
) -> dict[str, object]:
    if not current_user.check_user_group_allowed(request.user_group):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Group access denied")
    if not current_user.is_admin() and request.owner != current_user.user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Owner mismatch")
    return main_db.create_db_schema(request.model_dump()).__dict__


@router.post("/db_connection/")
def create_db_connection(
    request: CreateDBConnectionRequest,
    current_user: ArkanaUser = Depends(get_current_user),
    main_db: ArkanaMainDB = Depends(get_main_db),
) -> dict[str, object]:
    if not current_user.check_user_group_allowed(request.user_group):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Group access denied")
    if not current_user.is_admin() and request.owner != current_user.user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Owner mismatch")
    return main_db.create_db_connection(request.model_dump()).__dict__


@router.get("/db_connection/personal_user/")
def get_personal_user(
    db_id: int = Query(...),
    current_user: ArkanaUser = Depends(get_current_user),
) -> dict[str, object]:
    if not current_user.can_access_db(db_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    personal_user = current_user.get_private_db_user(db_id)
    if personal_user is None:
        return {"db_id": db_id, "personal_user": None}
    return {"db_id": db_id, "personal_user": personal_user.__dict__}


@router.post("/db_connection/personal_user/")
def create_personal_user(
    request: PersonalUserRequest,
    current_user: ArkanaUser = Depends(get_current_user),
) -> dict[str, object]:
    try:
        personal_user = current_user.create_private_db_user(
            db_id=request.db_id,
            arkana_user_id=request.arkana_user_id,
            db_user_name=request.db_user_name,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    return personal_user.__dict__


@router.post("/db_connection/user/{user_name}/password", response_model=PasswordStatusResponse)
def set_db_user_password(
    user_name: str,
    request: PasswordUpdateRequest,
    current_user: ArkanaUser = Depends(get_current_user),
) -> PasswordStatusResponse:
    try:
        current_user.set_private_db_password(request.db_id, user_name, request.password)
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    return PasswordStatusResponse(status="ok", keyring_service=current_user.main_db.config.keyring_service)
