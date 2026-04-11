from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class CreateDBRequest(BaseModel):
    user_group: int
    owner: str
    url: str | None = None
    ip: str | None = None
    db_name: str
    db_description: str | None = None
    db_con_id: int


class CreateDBConnectionRequest(BaseModel):
    user_group: int
    owner: str
    url: str | None = None
    ip: str | None = None
    server_description: str | None = None
    default_user: str | None = None
    admin_user: str | None = None
    db_type: str


class PersonalUserRequest(BaseModel):
    db_id: int
    arkana_user_id: str
    db_user_name: str


class PasswordUpdateRequest(BaseModel):
    db_id: int
    password: str = Field(min_length=1)


class KeyModelsRequest(BaseModel):
    start_tables: list[str] | None = None
    max_distance: int | None = Field(default=None, ge=0)
    include_all: bool = False


class FrameExecuteRequest(BaseModel):
    frame: dict[str, Any]
    input_parameters: dict[str, Any] = Field(default_factory=dict)
    referenced_frames: dict[str, dict[str, Any]] = Field(default_factory=dict)


class PasswordStatusResponse(BaseModel):
    status: str
    keyring_service: str


class FrameExecuteResponse(BaseModel):
    frame_id: int | None = None
    result: dict[str, Any]


class DashboardCellRequest(BaseModel):
    cell_key: str | None = None
    cell_type: str | None = None
    taggs: list[str] | str | None = None
    content: str | None = None
