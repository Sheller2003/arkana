from __future__ import annotations

import os
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status

from src.arkana_api_service.dependencies import get_current_user
from src.arkana_api_service.route_auth import require_route_auth
from src.arkana_api_service.routes.help_utils import build_help, with_help
from src.arkana_auth.user_object import ArkanaUser
from src.arkana_mdd_db.models import NotesChapterCreateRequest, NotesCreateRequest
from src.mdd_arkana_object.ark_notes import ArkanaNotes
from src.mdd_arkana_object.arkana_object_manager import ArkanaObjectManager

router = APIRouter(tags=["notes"])


MAX_UPLOAD_SIZE_BYTES = 10 * 1024 * 1024


def _resolve_notes_object(current_user: ArkanaUser, node_id: str) -> ArkanaNotes:
    normalized_node_id = str(node_id).strip()
    if normalized_node_id.startswith("tmp_"):
        buffer_id = normalized_node_id[len("tmp_") :]
        try:
            return ArkanaNotes.load_from_buffer(buffer_id)
        except KeyError as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Buffered notes not found") from exc

    try:
        object_id = int(normalized_node_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid notes identifier") from exc

    manager = ArkanaObjectManager(current_user)
    try:
        obj = manager.get_object(object_id).load()
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except OSError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    if not isinstance(obj, ArkanaNotes):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Object is not an ark_notes object")
    return obj


def _resolve_or_create_notes_object(current_user: ArkanaUser, node_id: str) -> ArkanaNotes:
    if str(node_id).strip() == "0":
        return ArkanaNotes(arkana_id=0, user_object=current_user, chapters=[])
    return _resolve_notes_object(current_user, node_id)


def _resolve_chapter(notes: ArkanaNotes, chapter_identifier: str) -> dict[str, object]:
    chapter = notes.get_chapter(chapter_identifier)
    if chapter is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chapter not found")
    return chapter


def _read_uploaded_file(file: UploadFile) -> tuple[str, bytes]:
    original_name = os.path.basename(str(file.filename or "").strip())
    if not original_name:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing file name")
    payload = file.file.read(MAX_UPLOAD_SIZE_BYTES + 1)
    if len(payload) > MAX_UPLOAD_SIZE_BYTES:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="File exceeds 10 MB")
    return original_name, payload


def _notes_storage_root() -> Path:
    return ArkanaNotes._object_storage_root()


def _note_storage_dir(notes: ArkanaNotes) -> Path:
    if notes.buffer_id:
        root = ArkanaNotes.get_buffer_directory(notes.buffer_id)
    else:
        root = _notes_storage_root() / str(notes.arkana_id)
    target = root / "files"
    target.mkdir(parents=True, exist_ok=True)
    return target


def _ensure_unique_file_name(target_dir: Path, file_name: str) -> str:
    candidate = file_name
    stem, suffix = os.path.splitext(file_name)
    counter = 1
    while (target_dir / candidate).exists():
        candidate = f"{stem}_{counter}{suffix}"
        counter += 1
    return candidate


@router.post("/notes")
def create_notes(
    request: NotesCreateRequest,
    current_user: ArkanaUser = Depends(get_current_user),
    help: bool = Query(default=False),
) -> dict[str, object]:
    require_route_auth(current_user, "create_notes")
    notes = ArkanaNotes(
        arkana_id=0,
        user_object=current_user,
        object_key=request.object_key,
        description=request.description,
        auth_group=request.auth_group,
        modeling_db=request.modeling_db,
        chapters=[],
    )
    for chapter in request.chapters:
        notes.append_chapter(
            key=chapter.key,
            content=str(chapter.content or ""),
            taggs=chapter.taggs,
            files=chapter.files,
        )
    notes.save()
    return with_help(
        notes.to_json(),
        help_enabled=help,
        help_payload=build_help(
            endpoint="/notes",
            method="POST",
            description="Creates a new buffered notes object. Buffered notes are stored for up to 24 hours until they are explicitly saved to the database.",
            query_parameters={"help": "Optional. If true, appends endpoint documentation to the response."},
            body="NotesCreateRequest JSON body.",
            returns="JSON object with buffered notes metadata and chapters.",
        ),
    )


@router.get("/notes/{object_id:int}/")
def get_notes(
    object_id: int,
    current_user: ArkanaUser = Depends(get_current_user),
    help: bool = Query(default=False),
) -> dict[str, object]:
    require_route_auth(current_user, "get_notes")
    notes = _resolve_notes_object(current_user, str(object_id))
    return with_help(
        notes.to_json(),
        help_enabled=help,
        help_payload=build_help(
            endpoint="/notes/{object_id}/",
            method="GET",
            description="Returns a persisted notes object including all chapters.",
            path_parameters={"object_id": "The persisted arkana notes object id."},
            query_parameters={"help": "Optional. If true, appends endpoint documentation to the response."},
            returns="JSON object with notes metadata and chapters.",
        ),
    )


@router.get("/notes/tmp_{buffer_id}/")
def get_tmp_notes(
    buffer_id: str,
    current_user: ArkanaUser = Depends(get_current_user),
    help: bool = Query(default=False),
) -> dict[str, object]:
    require_route_auth(current_user, "get_tmp_notes")
    notes = _resolve_notes_object(current_user, f"tmp_{buffer_id}")
    return with_help(
        notes.to_json(),
        help_enabled=help,
        help_payload=build_help(
            endpoint="/notes/tmp_{buffer_id}/",
            method="GET",
            description="Returns a buffered notes object stored for up to 24 hours.",
            path_parameters={"buffer_id": "The temporary notes buffer id."},
            query_parameters={"help": "Optional. If true, appends endpoint documentation to the response."},
            returns="JSON object with notes metadata and chapters.",
        ),
    )


@router.post("/notes/{note_id}/save")
def save_notes(
    note_id: str,
    current_user: ArkanaUser = Depends(get_current_user),
    help: bool = Query(default=False),
) -> dict[str, object]:
    require_route_auth(current_user, "save_notes")
    notes = _resolve_notes_object(current_user, note_id)
    if not notes.buffer_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only buffered notes can be saved")
    notes.user_object = current_user
    notes.save_to_db()
    return with_help(
        notes.to_json(),
        help_enabled=help,
        help_payload=build_help(
            endpoint="/notes/{note_id}/save",
            method="POST",
            description="Persists a buffered tmp_<id> notes object into the database.",
            path_parameters={"note_id": "A buffered notes identifier in the form tmp_<buffer_id>."},
            query_parameters={"help": "Optional. If true, appends endpoint documentation to the response."},
            returns="JSON object with the persisted notes metadata and chapters.",
        ),
    )


@router.post("/notes/{node_id}/chapter")
def create_notes_chapter(
    node_id: str,
    request: NotesChapterCreateRequest,
    current_user: ArkanaUser = Depends(get_current_user),
    help: bool = Query(default=False),
) -> dict[str, object]:
    require_route_auth(current_user, "create_notes_chapter")
    notes = _resolve_or_create_notes_object(current_user, node_id)
    created_ids: list[int] = []
    for chapter_request in request.chapters:
        created_ids.append(
            notes.append_chapter(
                key=chapter_request.key,
                content=str(chapter_request.content or ""),
                taggs=chapter_request.taggs,
                files=chapter_request.files,
            )
        )
    notes.save()
    return with_help(
        {
            "status": "ok",
            "created_chapter_ids": created_ids,
            "notes": notes.to_json(),
        },
        help_enabled=help,
        help_payload=build_help(
            endpoint="/notes/{node_id}/chapter",
            method="POST",
            description="Creates one or multiple chapters for a persisted or buffered notes object. Use node_id=0 to create a new buffered notes object.",
            path_parameters={"node_id": "A persisted notes id, tmp_<buffer_id>, or 0 for a new buffered notes object."},
            query_parameters={"help": "Optional. If true, appends endpoint documentation to the response."},
            body="NotesChapterCreateRequest JSON body.",
            returns="JSON object with created chapter ids and the updated notes payload.",
        ),
    )


@router.get("/notes/{node_id}/chapter/{chapter_identifier}")
def get_note_chapter(
    node_id: str,
    chapter_identifier: str,
    current_user: ArkanaUser = Depends(get_current_user),
    help: bool = Query(default=False),
) -> dict[str, object]:
    require_route_auth(current_user, "get_note_chapter")
    notes = _resolve_notes_object(current_user, node_id)
    chapter = _resolve_chapter(notes, chapter_identifier)
    return with_help(
        chapter,
        help_enabled=help,
        help_payload=build_help(
            endpoint="/notes/{node_id}/chapter/{chapter_identifier}",
            method="GET",
            description="Returns a chapter resolved by numeric chapter id or chapter key.",
            path_parameters={
                "node_id": "A persisted notes id or tmp_<buffer_id>.",
                "chapter_identifier": "A chapter id or chapter key.",
            },
            query_parameters={"help": "Optional. If true, appends endpoint documentation to the response."},
            returns="JSON object for the resolved chapter.",
        ),
    )


@router.get("/notes/{node_id}/chapter/{chapter_identifier}/files")
def get_note_chapter_files(
    node_id: str,
    chapter_identifier: str,
    current_user: ArkanaUser = Depends(get_current_user),
    help: bool = Query(default=False),
) -> dict[str, object]:
    require_route_auth(current_user, "get_note_chapter_files")
    notes = _resolve_notes_object(current_user, node_id)
    chapter = _resolve_chapter(notes, chapter_identifier)
    return with_help(
        {
            "chapter_id": chapter.get("chapter_id"),
            "key": chapter.get("key"),
            "files": chapter.get("files", []),
        },
        help_enabled=help,
        help_payload=build_help(
            endpoint="/notes/{node_id}/chapter/{chapter_identifier}/files",
            method="GET",
            description="Returns the files assigned to a chapter resolved by chapter id or key.",
            path_parameters={
                "node_id": "A persisted notes id or tmp_<buffer_id>.",
                "chapter_identifier": "A chapter id or chapter key.",
            },
            query_parameters={"help": "Optional. If true, appends endpoint documentation to the response."},
            returns="JSON object with chapter file entries.",
        ),
    )


@router.post("/notes/{node_id}/chapter/{chapter_identifier}/file")
def upload_note_chapter_file(
    node_id: str,
    chapter_identifier: str,
    file: UploadFile = File(...),
    current_user: ArkanaUser = Depends(get_current_user),
    help: bool = Query(default=False),
) -> dict[str, object]:
    require_route_auth(current_user, "upload_note_chapter_file")
    notes = _resolve_notes_object(current_user, node_id)
    chapter = _resolve_chapter(notes, chapter_identifier)
    original_name, payload = _read_uploaded_file(file)
    target_dir = _note_storage_dir(notes)
    stored_name = _ensure_unique_file_name(target_dir, original_name)
    (target_dir / stored_name).write_bytes(payload)

    current_files = list(chapter.get("files", []))
    current_files.append(stored_name)
    updated = notes.update_chapter(chapter_identifier, {"files": current_files})
    if updated is None:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Chapter could not be updated")
    notes.save()

    return with_help(
        {
            "status": "uploaded",
            "chapter": updated,
            "file_name": stored_name,
            "file_size": len(payload),
            "notes": notes.to_json(),
        },
        help_enabled=help,
        help_payload=build_help(
            endpoint="/notes/{node_id}/chapter/{chapter_identifier}/file",
            method="POST",
            description="Uploads a file up to 10 MB and assigns it to a notes chapter resolved by chapter id or key.",
            path_parameters={
                "node_id": "A persisted notes id or tmp_<buffer_id>.",
                "chapter_identifier": "A chapter id or chapter key.",
            },
            query_parameters={"help": "Optional. If true, appends endpoint documentation to the response."},
            body="multipart/form-data with a single file field named 'file'. Maximum 10 MB.",
            returns="JSON object with upload metadata and the updated notes payload.",
        ),
    )
