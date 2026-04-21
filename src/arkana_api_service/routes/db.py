from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status

from src.arkana_auth.user_object import ArkanaUser
from src.arkana_api_service.dependencies import get_current_user, get_main_db
from src.arkana_api_service.routes.help_utils import build_help, with_help
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
    help: bool = Query(default=False),
) -> dict[str, object]:
    db_record = main_db.get_db_schema(db_id)
    if db_record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Database not found")
    if not current_user.can_access_db(db_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    return with_help(
        db_record.__dict__,
        help_enabled=help,
        help_payload=build_help(
            endpoint="/db/{db_id}/",
            method="GET",
            description="Returns schema metadata for a database the user may access.",
            path_parameters={"db_id": "The database id."},
            query_parameters={"help": "Optional. If true, appends endpoint documentation to the response."},
            returns="JSON object with database schema metadata.",
        ),
    )


@router.get("/db/{db_id}/tables")
def get_db_tables(
    db_id: int,
    current_user: ArkanaUser = Depends(get_current_user),
    main_db: ArkanaMainDB = Depends(get_main_db),
    help: bool = Query(default=False),
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
    return with_help(
        {"db_id": db_id, "tables": visible_tables},
        help_enabled=help,
        help_payload=build_help(
            endpoint="/db/{db_id}/tables",
            method="GET",
            description="Lists visible tables for a database, excluding internal system tables.",
            path_parameters={"db_id": "The database id."},
            query_parameters={"help": "Optional. If true, appends endpoint documentation to the response."},
            returns="JSON object with the filtered table list.",
        ),
    )


@router.get("/database/{db_id}/table/{table_key}")
def get_database_table(
    db_id: int,
    table_key: str,
    current_user: ArkanaUser = Depends(get_current_user),
    main_db: ArkanaMainDB = Depends(get_main_db),
    help: bool = Query(default=False),
) -> dict[str, object]:
    if not current_user.can_access_db(db_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    try:
        table_info = main_db.get_table_info(db_id, table_key)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except NotImplementedError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return with_help(
        {
            "database_id": db_id,
            "table_key": table_key,
            **table_info,
        },
        help_enabled=help,
        help_payload=build_help(
            endpoint="/database/{db_id}/table/{table_key}",
            method="GET",
            description="Returns a JSON description of a specific table including its columns.",
            path_parameters={
                "db_id": "The database id.",
                "table_key": "The table name/key.",
            },
            query_parameters={"help": "Optional. If true, appends endpoint documentation to the response."},
            returns="JSON object with database_id, table_key, table_name and columns.",
        ),
    )


@router.post("/db/{db_id}/key_models")
def get_key_models(
    db_id: int,
    request: KeyModelsRequest,
    current_user: ArkanaUser = Depends(get_current_user),
    main_db: ArkanaMainDB = Depends(get_main_db),
    help: bool = Query(default=False),
) -> dict[str, object]:
    if not current_user.can_access_db(db_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    return with_help(
        main_db.build_key_models(
            db_id,
            start_tables=request.start_tables,
            max_distance=request.max_distance,
            include_all=request.include_all,
        ),
        help_enabled=help,
        help_payload=build_help(
            endpoint="/db/{db_id}/key_models",
            method="POST",
            description="Builds a key-model graph starting from one or more tables.",
            path_parameters={"db_id": "The database id."},
            query_parameters={"help": "Optional. If true, appends endpoint documentation to the response."},
            body="KeyModelsRequest JSON body.",
            returns="JSON object containing the derived key-model information.",
        ),
    )


@router.post("/db/")
def create_db(
    request: CreateDBRequest,
    current_user: ArkanaUser = Depends(get_current_user),
    main_db: ArkanaMainDB = Depends(get_main_db),
    help: bool = Query(default=False),
) -> dict[str, object]:
    if not current_user.check_user_group_allowed(request.user_group):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Group access denied")
    if not current_user.is_admin() and request.owner != current_user.user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Owner mismatch")
    return with_help(
        main_db.create_db_schema(request.model_dump()).__dict__,
        help_enabled=help,
        help_payload=build_help(
            endpoint="/db/",
            method="POST",
            description="Creates a new database schema record.",
            query_parameters={"help": "Optional. If true, appends endpoint documentation to the response."},
            body="CreateDBRequest JSON body.",
            returns="JSON object with the created database schema metadata.",
        ),
    )


@router.post("/db_connection/")
def create_db_connection(
    request: CreateDBConnectionRequest,
    current_user: ArkanaUser = Depends(get_current_user),
    main_db: ArkanaMainDB = Depends(get_main_db),
    help: bool = Query(default=False),
) -> dict[str, object]:
    if not current_user.check_user_group_allowed(request.user_group):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Group access denied")
    if not current_user.is_admin() and request.owner != current_user.user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Owner mismatch")
    return with_help(
        main_db.create_db_connection(request.model_dump()).__dict__,
        help_enabled=help,
        help_payload=build_help(
            endpoint="/db_connection/",
            method="POST",
            description="Creates a database connection record.",
            query_parameters={"help": "Optional. If true, appends endpoint documentation to the response."},
            body="CreateDBConnectionRequest JSON body.",
            returns="JSON object with the created connection metadata.",
        ),
    )


@router.get("/db_connection/personal_user/")
def get_personal_user(
    db_id: int = Query(...),
    current_user: ArkanaUser = Depends(get_current_user),
    help: bool = Query(default=False),
) -> dict[str, object]:
    if not current_user.can_access_db(db_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    personal_user = current_user.get_private_db_user(db_id)
    if personal_user is None:
        return with_help(
            {"db_id": db_id, "personal_user": None},
            help_enabled=help,
            help_payload=build_help(
                endpoint="/db_connection/personal_user/",
                method="GET",
                description="Returns the personal DB user for the current user and database.",
                query_parameters={
                    "db_id": "The database id.",
                    "help": "Optional. If true, appends endpoint documentation to the response.",
                },
                returns="JSON object with the personal user or null.",
            ),
        )
    return with_help(
        {"db_id": db_id, "personal_user": personal_user.__dict__},
        help_enabled=help,
        help_payload=build_help(
            endpoint="/db_connection/personal_user/",
            method="GET",
            description="Returns the personal DB user for the current user and database.",
            query_parameters={
                "db_id": "The database id.",
                "help": "Optional. If true, appends endpoint documentation to the response.",
            },
            returns="JSON object with the personal user or null.",
        ),
    )


@router.post("/db_connection/personal_user/")
def create_personal_user(
    request: PersonalUserRequest,
    current_user: ArkanaUser = Depends(get_current_user),
    help: bool = Query(default=False),
) -> dict[str, object]:
    try:
        personal_user = current_user.create_private_db_user(
            db_id=request.db_id,
            arkana_user_id=request.arkana_user_id,
            db_user_name=request.db_user_name,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    return with_help(
        personal_user.__dict__,
        help_enabled=help,
        help_payload=build_help(
            endpoint="/db_connection/personal_user/",
            method="POST",
            description="Creates a personal DB user for the authenticated user.",
            query_parameters={"help": "Optional. If true, appends endpoint documentation to the response."},
            body="PersonalUserRequest JSON body.",
            returns="JSON object with the created personal DB user.",
        ),
    )


@router.post("/db_connection/user/{user_name}/password")
def set_db_user_password(
    user_name: str,
    request: PasswordUpdateRequest,
    current_user: ArkanaUser = Depends(get_current_user),
    help: bool = Query(default=False),
) -> dict[str, object]:
    try:
        current_user.set_private_db_password(request.db_id, user_name, request.password)
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    return with_help(
        PasswordStatusResponse(status="ok", keyring_service=current_user.main_db.config.keyring_service),
        help_enabled=help,
        help_payload=build_help(
            endpoint="/db_connection/user/{user_name}/password",
            method="POST",
            description="Stores or updates a password for a private database user in the configured keyring.",
            path_parameters={"user_name": "The database user name."},
            query_parameters={"help": "Optional. If true, appends endpoint documentation to the response."},
            body="PasswordUpdateRequest JSON body.",
            returns="JSON object with the update status.",
        ),
    )
