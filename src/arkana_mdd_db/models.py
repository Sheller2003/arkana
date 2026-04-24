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


class CreateGroupRequest(BaseModel):
    group_name: str = Field(min_length=1)


class AssignGroupRequest(BaseModel):
    user_id: str = Field(min_length=1)


class FrameExecuteResponse(BaseModel):
    frame_id: int | None = None
    result: dict[str, Any]


class ReportCellRequest(BaseModel):
    cell_key: str | None = None
    cell_type: str | None = None
    taggs: list[str] | str | None = None
    content: str | None = None


class ReportCreateRequest(BaseModel):
    public: bool = True
    auth_group: int = Field(default=0, ge=0)
    object_key: str | None = None
    description: str | None = None
    arkana_group: int | None = None
    cells: list[ReportCellRequest] = Field(default_factory=list)


class NotesChapterRequest(BaseModel):
    key: str = Field(min_length=1)
    taggs: list[str] | str | None = None
    content: str | None = None
    files: list[str] | str | None = None


class NotesChapterCreateRequest(BaseModel):
    chapters: list[NotesChapterRequest] = Field(min_length=1)


class NotesCreateRequest(BaseModel):
    object_key: str | None = None
    description: str | None = None
    auth_group: int = Field(default=0, ge=0)
    modeling_db: int = Field(default=0, ge=0)
    chapters: list[NotesChapterRequest] = Field(default_factory=list)
