from __future__ import annotations

import math
import os
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse, HTMLResponse, PlainTextResponse, RedirectResponse

from src.arkana_api_service.dependencies import get_current_user
from src.arkana_api_service.route_auth import require_route_auth
from src.arkana_api_service.routes.help_utils import build_help, with_help
from src.arkana_auth.amezitUserObject import AmezitUserObject
from src.arkana_auth.amezit_supabase_service import AmezitSupabaseService, SupabaseClientError
from src.arkana_auth.user_object import ArkanaUser
from src.arkana_mdd_db.config import load_env
from src.arkana_mdd_db.models import ReportCellRequest, ReportCreateRequest
from src.arkana_sphere.arkana_session_manager import ArkanaSessionManager
from src.mdd_arkana_object.cell_types import CellType
from src.mdd_arkana_object.ark_report import ArkanaReport
from src.mdd_arkana_object.arkana_object_manager import ArkanaObjectManager

router = APIRouter(tags=["report"])


MAX_UPLOAD_SIZE_BYTES = 10 * 1024 * 1024
ALLOWED_UPLOAD_SUFFIXES = {"csv", "json"}
ALLOWED_REPORT_UPLOAD_SUFFIXES = {"csv", "json", "py", "r", "rdata"}


def _delete_arkana_object(arkana_id: int) -> None:
    _, cursor = ArkanaReport()._ensure_cursor()
    cursor.execute("DELETE FROM arkana_object WHERE arkana_id = %s", (int(arkana_id),))
    ArkanaReport._commit()


def _upsert_arkana_object_file(
    *,
    arkana_id: int,
    file_name: str,
    file_type: str,
    owner: str,
    file_size_bytes: int,
) -> None:
    file_size_kb = max(1, math.ceil(file_size_bytes / 1024))
    _, cursor = ArkanaReport()._ensure_cursor()
    cursor.execute(
        """
        SELECT file_id
        FROM arkana_object_file
        WHERE assigned_to_arkana_id = %s AND file_name = %s
        LIMIT 1
        """,
        (int(arkana_id), str(file_name)),
    )
    row = cursor.fetchone()
    if row is None:
        cursor.execute(
            """
            INSERT INTO arkana_object_file
                (file_name, file_type, assigned_to_arkana_id, owner, tmp, file_size)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (str(file_name), str(file_type), int(arkana_id), str(owner), 0, int(file_size_kb)),
        )
    else:
        cursor.execute(
            """
            UPDATE arkana_object_file
            SET file_type = %s,
                owner = %s,
                tmp = %s,
                file_size = %s,
                changed_at = CURRENT_TIMESTAMP
            WHERE file_id = %s
            """,
            (str(file_type), str(owner), 0, int(file_size_kb), int(row[0])),
    )
    ArkanaReport._commit()


def _delete_arkana_object_file_record(*, arkana_id: int, file_name: str) -> None:
    _, cursor = ArkanaReport()._ensure_cursor()
    cursor.execute(
        "DELETE FROM arkana_object_file WHERE assigned_to_arkana_id = %s AND file_name = %s",
        (int(arkana_id), str(file_name)),
    )
    ArkanaReport._commit()


def _get_root_path() -> str:
    load_env()
    return os.getenv("ROOT_PATH", "http://127.0.0.1:8000").rstrip("/")


def _normalize_file_content(arkana_id: int, content: str) -> str:
    normalized_content = str(content or "").strip()
    if not normalized_content:
        return normalized_content
    root_path = _get_root_path()
    if normalized_content.startswith(("http://", "https://")):
        parsed = urlparse(normalized_content)
        file_name = parsed.path.rstrip("/").split("/")[-1]
        if file_name:
            return f"{root_path}/report/{arkana_id}/files/{file_name}"
        return normalized_content
    return f"{root_path}/report/{arkana_id}/files/{normalized_content}"


def _extract_file_name(content: str) -> str:
    normalized_content = str(content or "").strip()
    if not normalized_content:
        return ""
    if normalized_content.startswith(("http://", "https://")):
        parsed = urlparse(normalized_content)
        return parsed.path.rstrip("/").split("/")[-1]
    return normalized_content.split("/")[-1]


def _report_has_other_file_reference(report: ArkanaReport, *, excluded_cell_id: int | None, file_name: str) -> bool:
    if report.cells is None:
        return False
    normalized_file_name = _extract_file_name(file_name)
    for candidate in report.cells:
        if not CellType.is_workspace_file_reference_type(str(candidate.get("cell_type") or "")):
            continue
        candidate_cell_id = candidate.get("cell_id")
        if excluded_cell_id is not None and candidate_cell_id == excluded_cell_id:
            continue
        candidate_file_name = _extract_file_name(str(candidate.get("content") or ""))
        if candidate_file_name == normalized_file_name:
            return True
    return False


def _delete_report_file_if_unreferenced(
    *,
    report: ArkanaReport,
    arkana_id: int,
    current_user: ArkanaUser,
    file_name: str,
    excluded_cell_id: int | None,
) -> None:
    if not file_name:
        return
    if _report_has_other_file_reference(report, excluded_cell_id=excluded_cell_id, file_name=file_name):
        return
    session_manager = ArkanaSessionManager()
    file_info = session_manager.get_session_file(
        arkana_object_id=arkana_id,
        user_object=current_user,
        file_name=file_name,
        endings=(".csv", ".txt", ".png", ".json", ".jpg", ".jpeg", ".rdata", ".RData"),
    )
    if file_info is not None:
        try:
            os.remove(file_info["absolute_path"])
        except FileNotFoundError:
            pass
    _delete_arkana_object_file_record(arkana_id=arkana_id, file_name=file_name)


def _read_uploaded_file(file: UploadFile, *, allowed_suffixes: set[str]) -> tuple[str, str, bytes]:
    original_name = os.path.basename(str(file.filename or "").strip())
    if not original_name:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing file name")
    file_suffix = original_name.rsplit(".", 1)[-1].lower() if "." in original_name else ""
    if file_suffix not in allowed_suffixes:
        allowed_list = ", ".join(sorted(allowed_suffixes))
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Only {allowed_list} uploads are allowed")
    payload = file.file.read(MAX_UPLOAD_SIZE_BYTES + 1)
    if len(payload) > MAX_UPLOAD_SIZE_BYTES:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="File exceeds 10 MB")
    return original_name, file_suffix, payload


def _store_uploaded_report_file(
    *,
    arkana_id: int,
    current_user: ArkanaUser,
    file_name: str,
    payload: bytes,
) -> None:
    session_manager = ArkanaSessionManager()
    workspace_path = session_manager.get_workspace_path(arkana_object_id=arkana_id, user_object=current_user)
    workspace_path.mkdir(parents=True, exist_ok=True)
    target_path = workspace_path / file_name
    target_path.write_bytes(payload)


def _normalize_cell_for_api(arkana_id: int, cell: dict[str, object]) -> dict[str, object]:
    normalized = dict(cell)
    cell_type = str(normalized.get("cell_type") or "").lower()
    if CellType.is_workspace_file_reference_type(cell_type):
        content = str(normalized.get("content") or "").strip()
        if content:
            if cell_type == CellType.FILE.value:
                normalized["cell_type"] = CellType.infer_file_type(content, default=CellType.FILE.value)
            normalized["content"] = _normalize_file_content(arkana_id, content)
    child_cells = normalized.get("cells")
    if isinstance(child_cells, list):
        normalized["cells"] = [
            _normalize_cell_for_api(arkana_id, child)
            for child in child_cells
            if isinstance(child, dict)
        ]
    return normalized


@router.get("/report/{arkana_id}")
def get_report(
    arkana_id: int,
    current_user: ArkanaUser = Depends(get_current_user),
    help: bool = Query(default=False),
) -> dict[str, object]:
    require_route_auth(current_user, "get_report")
    manager = ArkanaObjectManager(current_user)
    try:
        report = manager.get_object(arkana_id).load()
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except OSError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except RuntimeError as exc:
        # Typically raised when a required MySQL connection/cursor cannot be initialized
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Database unavailable: {exc}",
        ) from exc
    return with_help(
        _normalize_cell_for_api(arkana_id, report.to_json()),
        help_enabled=help,
        help_payload=build_help(
            endpoint="/report/{arkana_id}",
            method="GET",
            description="Returns a report including its top-level cells and dependent sub-cells.",
            path_parameters={"arkana_id": "The report object id."},
            query_parameters={"help": "Optional. If true, appends endpoint documentation to the response."},
            returns="JSON object with report metadata and cells.",
        ),
    )


@router.post("/report")
def create_report(
    request: ReportCreateRequest,
    current_user: ArkanaUser = Depends(get_current_user),
    help: bool = Query(default=False),
) -> dict[str, object]:
    require_route_auth(current_user, "create_report")
    is_public = bool(request.public)
    auth_group = 0 if is_public else None
    arkana_group = 0 if is_public else None
    if not is_public and not isinstance(current_user, AmezitUserObject):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Supabase login required for private reports",
        )
    if not is_public and not current_user.supabase_access_token:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Supabase access token required for private reports",
        )

    report = ArkanaReport(
        arkana_type="report",
        auth_group=auth_group,
        object_key=request.object_key,
        description=request.description,
        arkana_group=arkana_group,
        user_object=current_user,
    )
    report.cells = []
    for cell_request in request.cells:
        payload = cell_request.model_dump(exclude_none=True)
        report.append_cell(
            cell_type=str(payload.pop("cell_type", "text")),
            payload=payload.get("content"),
            taggs=payload.get("taggs"),
        )
        if report.cells:
            latest = report.cells[-1]
            if payload.get("cell_key") is not None:
                latest["cell_key"] = payload["cell_key"]
    report.save()
    if not is_public:
        try:
            group_id = AmezitSupabaseService.from_env().create_group(
                group_name=str(report.arkana_id),
                is_object=True,
                access_token=current_user.supabase_access_token,
            )
        except SupabaseClientError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
        report.auth_group = int(group_id)
        report.arkana_group = int(group_id)
        report.save()
    return with_help(
        _normalize_cell_for_api(int(report.arkana_id), report.to_json()),
        help_enabled=help,
        help_payload=build_help(
            endpoint="/report",
            method="POST",
            description="Creates a new report and optionally seeds it with initial cells.",
            query_parameters={"help": "Optional. If true, appends endpoint documentation to the response."},
            body="ReportCreateRequest JSON body.",
            returns="JSON object with the created report.",
        ),
    )


def _load_report(current_user: ArkanaUser, arkana_id: int) -> ArkanaReport:
    manager = ArkanaObjectManager(current_user)
    try:
        report = manager.get_object(arkana_id).load()
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except OSError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except RuntimeError as exc:
        # Surface DB connectivity issues as 503 instead of generic 500
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Database unavailable: {exc}",
        ) from exc

    if not isinstance(report, ArkanaReport):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Object is not a report")
    return report


def _ensure_object_group_access(current_user: ArkanaUser, arkana_id: int) -> None:
    manager = ArkanaObjectManager(current_user)
    try:
        manager.get_object(arkana_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except OSError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Database unavailable: {exc}",
        ) from exc


def _get_report_sessions_for_user(arkana_id: int, current_user: ArkanaUser) -> list[dict[str, object]]:
    _ensure_object_group_access(current_user, arkana_id)
    session_manager = ArkanaSessionManager()
    sessions = session_manager.get_object_sessions(arkana_id, user_object=current_user)
    normalized_sessions: list[dict[str, object]] = []
    for session in sessions:
        normalized_sessions.append(
            {
                "session_id": str(session.get("session_id") or ""),
                "container_name": str(session.get("container_name") or ""),
                "runtime_type": str(session.get("runtime_type") or "py"),
                "language": str(session.get("language") or ""),
                "user_id": str(session.get("user_id") or ""),
                "arkana_object_id": str(session.get("arkana_object_id") or ""),
                "workspace_path": str(session.get("workspace_path") or ""),
                "created_at": session.get("created_at"),
                "expires_at": session.get("expires_at"),
                "lifetime_seconds": session.get("lifetime_seconds"),
            }
        )
    return normalized_sessions


def _cell_get_response(cell: dict[str, object]):
    cell_type = str(cell.get("cell_type") or "").lower()
    content = cell.get("content")

    if CellType.is_workspace_file_reference_type(cell_type):
        target_url = str(content or "").strip()
        if not target_url:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File URL not found")
        return RedirectResponse(url=target_url, status_code=status.HTTP_307_TEMPORARY_REDIRECT)

    if cell_type == "html":
        return HTMLResponse(content=str(content or ""))

    if cell_type in {"md", "text"}:
        return PlainTextResponse(content=str(content or ""))

    return cell


@router.get("/report/{arkana_id}/cell/{cell_identifier}")
def get_report_cell(
    arkana_id: int,
    cell_identifier: str,
    cell_id: int | None = Query(default=None, ge=1),
    current_user: ArkanaUser = Depends(get_current_user),
    help: bool = Query(default=False),
) -> dict[str, object]:
    require_route_auth(current_user, "get_report_cell")
    report = _load_report(current_user, arkana_id)
    if cell_identifier == "get" and cell_id is not None:
        cell = report.get_cell_by_id(cell_id)
        if cell is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cell not found")
        normalized_cell = _normalize_cell_for_api(arkana_id, cell)
        if help:
            return with_help(
                normalized_cell,
                help_enabled=True,
                help_payload=build_help(
                    endpoint="/report/{arkana_id}/cell/get",
                    method="GET",
                    description="Resolves a cell by exact cell_id and returns content according to its type.",
                    path_parameters={"arkana_id": "The report object id."},
                    query_parameters={
                        "cell_id": "The exact internal cell id.",
                        "help": "Optional. If true, appends endpoint documentation to the response.",
                    },
                    returns="JSON metadata when help=true, otherwise redirect/html/plain text/cell JSON depending on cell_type.",
                ),
            )
        return _cell_get_response(normalized_cell)
    cell = report.get_cell_by_id(cell_id) if cell_id is not None else report.get_cell(cell_identifier)
    if cell is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cell not found")
    return with_help(
        _normalize_cell_for_api(arkana_id, cell),
        help_enabled=help,
        help_payload=build_help(
            endpoint="/report/{arkana_id}/cell/{cell_identifier}",
            method="GET",
            description="Returns a single cell as JSON. Numeric path identifiers address the visible top-level index; strings address cell_key.",
            path_parameters={
                "arkana_id": "The report object id.",
                "cell_identifier": "A top-level index or cell_key.",
            },
            query_parameters={
                "cell_id": "Optional exact internal cell id. If present it overrides cell_identifier.",
                "help": "Optional. If true, appends endpoint documentation to the response.",
            },
            returns="JSON object for the resolved cell.",
        ),
    )


@router.get("/report/{arkana_id}/cell")
@router.get("/report/{arkana_id}/cell/")
def get_report_cell_by_id(
    arkana_id: int,
    cell_id: int = Query(..., ge=1),
    current_user: ArkanaUser = Depends(get_current_user),
    help: bool = Query(default=False),
) -> dict[str, object]:
    require_route_auth(current_user, "get_report_cell_by_id")
    report = _load_report(current_user, arkana_id)
    cell = report.get_cell_by_id(cell_id)
    if cell is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cell not found")
    return with_help(
        _normalize_cell_for_api(arkana_id, cell),
        help_enabled=help,
        help_payload=build_help(
            endpoint="/report/{arkana_id}/cell",
            method="GET",
            description="Returns a cell by its exact internal cell_id.",
            path_parameters={"arkana_id": "The report object id."},
            query_parameters={
                "cell_id": "The exact internal cell id.",
                "help": "Optional. If true, appends endpoint documentation to the response.",
            },
            returns="JSON object for the resolved cell.",
        ),
    )


@router.get("/report/{arkana_id}/cell/get")
def get_report_cell_content_by_id(
    arkana_id: int,
    cell_id: int = Query(..., ge=1),
    current_user: ArkanaUser = Depends(get_current_user),
    help: bool = Query(default=False),
):
    require_route_auth(current_user, "get_report_cell_content_by_id")
    report = _load_report(current_user, arkana_id)
    cell = report.get_cell_by_id(cell_id)
    if cell is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cell not found")
    normalized_cell = _normalize_cell_for_api(arkana_id, cell)
    if help:
        return with_help(
            normalized_cell,
            help_enabled=True,
            help_payload=build_help(
                endpoint="/report/{arkana_id}/cell/get",
                method="GET",
                description="Returns cell content by exact cell_id. File cells redirect, html returns HTML, md/text return plain text.",
                path_parameters={"arkana_id": "The report object id."},
                query_parameters={
                    "cell_id": "The exact internal cell id.",
                    "help": "Optional. If true, appends endpoint documentation to the response.",
                },
                returns="JSON metadata when help=true, otherwise redirect/html/plain text/cell JSON depending on cell_type.",
            ),
        )
    return _cell_get_response(normalized_cell)


@router.get("/report/{arkana_id}/cell/{cell_identifier}/get")
def get_report_cell_content(
    arkana_id: int,
    cell_identifier: str,
    current_user: ArkanaUser = Depends(get_current_user),
    help: bool = Query(default=False),
):
    require_route_auth(current_user, "get_report_cell_content")
    report = _load_report(current_user, arkana_id)
    cell = report.get_cell(cell_identifier)
    if cell is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cell not found")
    normalized_cell = _normalize_cell_for_api(arkana_id, cell)
    if help:
        return with_help(
            normalized_cell,
            help_enabled=True,
            help_payload=build_help(
                endpoint="/report/{arkana_id}/cell/{cell_identifier}/get",
                method="GET",
                description="Returns cell content by top-level index or cell_key. File cells redirect, html returns HTML, md/text return plain text.",
                path_parameters={
                    "arkana_id": "The report object id.",
                    "cell_identifier": "A top-level index or cell_key.",
                },
                query_parameters={"help": "Optional. If true, appends endpoint documentation to the response."},
                returns="JSON metadata when help=true, otherwise redirect/html/plain text/cell JSON depending on cell_type.",
            ),
        )
    return _cell_get_response(normalized_cell)


@router.get("/report/{arkana_id}/files")
def get_report_files(
    arkana_id: int,
    current_user: ArkanaUser = Depends(get_current_user),
    help: bool = Query(default=False),
) -> dict[str, object]:
    require_route_auth(current_user, "get_report_files")
    _ensure_object_group_access(current_user, arkana_id)
    session_manager = ArkanaSessionManager()
    files = session_manager.get_session_files(
        arkana_object_id=arkana_id,
        user_object=current_user,
        endings=(".csv", ".txt", ".png"),
    )
    root_path = _get_root_path()
    file_entries = [
        {
            "file_name": file_info["file_name"],
            "file_url": f"{root_path}/report/{arkana_id}/files/{file_info['file_name']}",
        }
        for file_info in files
    ]
    return with_help(
        {"arkana_object_id": arkana_id, "files": file_entries},
        help_enabled=help,
        help_payload=build_help(
            endpoint="/report/{arkana_id}/files",
            method="GET",
            description="Lists exported report files with allowed endings .csv, .txt and .png.",
            path_parameters={"arkana_id": "The report object id."},
            query_parameters={"help": "Optional. If true, appends endpoint documentation to the response."},
            returns="JSON object with file_name and file_url entries.",
        ),
    )


@router.get("/report/{arkana_id}/files/{file_name}")
def get_report_file(
    arkana_id: int,
    file_name: str,
    current_user: ArkanaUser = Depends(get_current_user),
    help: bool = Query(default=False),
):
    require_route_auth(current_user, "get_report_file")
    _ensure_object_group_access(current_user, arkana_id)
    session_manager = ArkanaSessionManager()
    file_info = session_manager.get_session_file(
        arkana_object_id=arkana_id,
        user_object=current_user,
        file_name=file_name,
        endings=(".csv", ".txt", ".png"),
    )
    if file_info is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")
    if help:
        return with_help(
            {
                "arkana_object_id": arkana_id,
                "file_name": file_info["file_name"],
                "file_url": f"{_get_root_path()}/report/{arkana_id}/files/{file_info['file_name']}",
            },
            help_enabled=True,
            help_payload=build_help(
                endpoint="/report/{arkana_id}/files/{file_name}",
                method="GET",
                description="Returns a stored report file. When help=true, metadata is returned instead of the file stream.",
                path_parameters={
                    "arkana_id": "The report object id.",
                    "file_name": "The file name inside the report workspace.",
                },
                query_parameters={"help": "Optional. If true, appends endpoint documentation to the response."},
                returns="File response normally, JSON metadata when help=true.",
            ),
        )
    return FileResponse(path=file_info["absolute_path"], filename=file_info["file_name"])


@router.get("/report/{arkana_id}/sessions")
def get_report_sessions(
    arkana_id: int,
    current_user: ArkanaUser = Depends(get_current_user),
    help: bool = Query(default=False),
) -> dict[str, object]:
    require_route_auth(current_user, "get_report_sessions")
    sessions = _get_report_sessions_for_user(arkana_id, current_user)
    return with_help(
        {"arkana_object_id": arkana_id, "sessions": sessions},
        help_enabled=help,
        help_payload=build_help(
            endpoint="/report/{arkana_id}/sessions",
            method="GET",
            description="Lists all runtime sessions for the authenticated user within the report.",
            path_parameters={"arkana_id": "The report object id."},
            query_parameters={"help": "Optional. If true, appends endpoint documentation to the response."},
            returns="JSON object with session metadata for the current user and report.",
        ),
    )


@router.post("/report/{arkana_id}/sessions")
def restart_report_sessions(
    arkana_id: int,
    current_user: ArkanaUser = Depends(get_current_user),
    help: bool = Query(default=False),
) -> dict[str, object]:
    require_route_auth(current_user, "restart_report_sessions")
    _ensure_object_group_access(current_user, arkana_id)
    session_manager = ArkanaSessionManager()
    previous_sessions = _get_report_sessions_for_user(arkana_id, current_user)
    restarted_sessions = session_manager.restart_object_sessions(arkana_id, user_object=current_user)
    return with_help(
        {
            "arkana_object_id": arkana_id,
            "previous_sessions": previous_sessions,
            "restarted_sessions": restarted_sessions,
            "status": "restarted",
        },
        help_enabled=help,
        help_payload=build_help(
            endpoint="/report/{arkana_id}/sessions",
            method="POST",
            description="Deletes and recreates all runtime session containers for the authenticated user within the report.",
            path_parameters={"arkana_id": "The report object id."},
            query_parameters={"help": "Optional. If true, appends endpoint documentation to the response."},
            returns="JSON object with previous and recreated session metadata.",
        ),
    )


@router.put("/report/{arkana_id}/cell/{cell_identifier}")
def update_report_cell(
    arkana_id: int,
    cell_identifier: str,
    request: ReportCellRequest,
    current_user: ArkanaUser = Depends(get_current_user),
    help: bool = Query(default=False),
) -> dict[str, object]:
    require_route_auth(current_user, "update_report_cell")
    report = _load_report(current_user, arkana_id)
    payload = request.model_dump(exclude_none=True)
    report.update_cell(cell_identifier, payload)
    cell = report.get_cell(cell_identifier)
    if cell is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cell not found")
    report.save()
    result_cell = report.get_cell(cell_identifier) or cell
    return with_help(
        _normalize_cell_for_api(arkana_id, result_cell),
        help_enabled=help,
        help_payload=build_help(
            endpoint="/report/{arkana_id}/cell/{cell_identifier}",
            method="PUT",
            description="Updates a cell by top-level index or cell_key.",
            path_parameters={
                "arkana_id": "The report object id.",
                "cell_identifier": "A top-level index or cell_key.",
            },
            query_parameters={"help": "Optional. If true, appends endpoint documentation to the response."},
            body="ReportCellRequest JSON body.",
            returns="JSON object for the updated cell.",
        ),
    )


@router.delete("/report/{arkana_id}/cell/{cell_identifier}")
def delete_report_cell(
    arkana_id: int,
    cell_identifier: str,
    current_user: ArkanaUser = Depends(get_current_user),
    help: bool = Query(default=False),
) -> dict[str, object]:
    require_route_auth(current_user, "delete_report_cell")
    report = _load_report(current_user, arkana_id)
    cell = report.get_cell(cell_identifier)
    if cell is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cell not found")
    if CellType.is_workspace_file_reference_type(str(cell.get("cell_type") or "")):
        file_name = _extract_file_name(str(cell.get("content") or ""))
        cell_id = cell.get("cell_id")
        _delete_report_file_if_unreferenced(
            report=report,
            arkana_id=arkana_id,
            current_user=current_user,
            file_name=file_name,
            excluded_cell_id=int(cell_id) if cell_id not in (None, "") else None,
        )
    report.delete_cell(cell_identifier).save()
    return with_help(
        {"status": "deleted", "cell": cell},
        help_enabled=help,
        help_payload=build_help(
            endpoint="/report/{arkana_id}/cell/{cell_identifier}",
            method="DELETE",
            description="Deletes a cell by top-level index or cell_key.",
            path_parameters={
                "arkana_id": "The report object id.",
                "cell_identifier": "A top-level index or cell_key.",
            },
            query_parameters={"help": "Optional. If true, appends endpoint documentation to the response."},
            returns="JSON object with the deleted cell payload.",
        ),
    )


@router.post("/report/{arkana_id}/cell/{cell_identifier}/upload")
def upload_report_cell_file(
    arkana_id: int,
    cell_identifier: str,
    file: UploadFile = File(...),
    current_user: ArkanaUser = Depends(get_current_user),
    help: bool = Query(default=False),
) -> dict[str, object]:
    require_route_auth(current_user, "upload_report_cell_file")
    report = _load_report(current_user, arkana_id)
    cell = report.get_cell(cell_identifier)
    if cell is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cell not found")
    if not CellType.is_file_type(str(cell.get("cell_type") or "")):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cell must be a file cell")

    original_name, file_suffix, payload = _read_uploaded_file(file, allowed_suffixes=ALLOWED_UPLOAD_SUFFIXES)
    _store_uploaded_report_file(
        arkana_id=arkana_id,
        current_user=current_user,
        file_name=original_name,
        payload=payload,
    )

    previous_file_name = _extract_file_name(str(cell.get("content") or ""))
    cell_id = cell.get("cell_id")
    report.update_cell(
        cell_identifier,
        {
            "content": original_name,
            "cell_type": CellType.FILE.value,
        },
    ).save()
    updated_cell = report.get_cell(cell_identifier)
    if updated_cell is None:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Uploaded file cell could not be reloaded")

    _upsert_arkana_object_file(
        arkana_id=arkana_id,
        file_name=original_name,
        file_type=file_suffix,
        owner=current_user.user_id,
        file_size_bytes=len(payload),
    )

    if previous_file_name and previous_file_name != original_name:
        _delete_report_file_if_unreferenced(
            report=report,
            arkana_id=arkana_id,
            current_user=current_user,
            file_name=previous_file_name,
            excluded_cell_id=int(cell_id) if cell_id not in (None, "") else None,
        )

    return with_help(
        {
            "status": "uploaded",
            "arkana_object_id": arkana_id,
            "cell": _normalize_cell_for_api(arkana_id, updated_cell),
            "file_name": original_name,
            "file_size": len(payload),
        },
        help_enabled=help,
        help_payload=build_help(
            endpoint="/report/{arkana_id}/cell/{cell_identifier}/upload",
            method="POST",
            description="Uploads a csv or json file into the report workspace and assigns it to an existing file cell.",
            path_parameters={
                "arkana_id": "The report object id.",
                "cell_identifier": "A cell id or cell_key for an existing file cell.",
            },
            query_parameters={"help": "Optional. If true, appends endpoint documentation to the response."},
            body="multipart/form-data with a single file field named 'file'. Maximum 10 MB.",
            returns="JSON object with the updated file cell and uploaded file metadata.",
        ),
    )


@router.post("/report/{arkana_id}/upload")
def upload_report_file(
    arkana_id: int,
    file: UploadFile = File(...),
    current_user: ArkanaUser = Depends(get_current_user),
    help: bool = Query(default=False),
) -> dict[str, object]:
    require_route_auth(current_user, "upload_report_file")
    report = _load_report(current_user, arkana_id)
    original_name, file_suffix, payload = _read_uploaded_file(file, allowed_suffixes=ALLOWED_REPORT_UPLOAD_SUFFIXES)
    if file_suffix in {"py", "r"}:
        try:
            code_content = payload.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Code upload must be valid UTF-8 text") from exc
        target_cell_type = CellType.PY_CODE.value if file_suffix == "py" else CellType.R_CODE.value
        report.append_cell(
            cell_type=target_cell_type,
            payload=code_content,
        )
        report.save()
        created_cell = report.cells[-1] if report.cells else None
        if created_cell is None:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Uploaded code cell could not be created")
        return with_help(
            {
                "status": "uploaded",
                "arkana_object_id": arkana_id,
                "cell": _normalize_cell_for_api(arkana_id, created_cell),
                "file_name": original_name,
                "file_size": len(payload),
            },
            help_enabled=help,
            help_payload=build_help(
                endpoint="/report/{arkana_id}/upload",
                method="POST",
                description="Uploads csv/json files as file cells or py/r files as executable code cells.",
                path_parameters={"arkana_id": "The report object id."},
                query_parameters={"help": "Optional. If true, appends endpoint documentation to the response."},
                body="multipart/form-data with a single file field named 'file'. Maximum 10 MB.",
                returns="JSON object with the created cell and uploaded file metadata.",
            ),
        )

    _store_uploaded_report_file(
        arkana_id=arkana_id,
        current_user=current_user,
        file_name=original_name,
        payload=payload,
    )

    created_cell_type = CellType.RDATA.value if file_suffix == "rdata" else CellType.FILE.value
    report.append_cell(
        cell_type=created_cell_type,
        payload=original_name,
    )
    report.save()
    created_cell = report.cells[-1] if report.cells else None
    if created_cell is None:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Uploaded file cell could not be created")

    _upsert_arkana_object_file(
        arkana_id=arkana_id,
        file_name=original_name,
        file_type=file_suffix,
        owner=current_user.user_id,
        file_size_bytes=len(payload),
    )

    return with_help(
        {
            "status": "uploaded",
            "arkana_object_id": arkana_id,
            "cell": _normalize_cell_for_api(arkana_id, report.get_cell(created_cell.get("cell_key")) or created_cell),
            "file_name": original_name,
            "file_size": len(payload),
        },
        help_enabled=help,
        help_payload=build_help(
            endpoint="/report/{arkana_id}/upload",
            method="POST",
            description="Uploads csv/json files as file cells, rdata files as rdata cells, or py/r files as executable code cells.",
            path_parameters={"arkana_id": "The report object id."},
            query_parameters={"help": "Optional. If true, appends endpoint documentation to the response."},
            body="multipart/form-data with a single file field named 'file'. Maximum 10 MB.",
            returns="JSON object with the created file cell and uploaded file metadata.",
        ),
    )


@router.delete("/report/{arkana_id}")
def delete_report(
    arkana_id: int,
    current_user: ArkanaUser = Depends(get_current_user),
    help: bool = Query(default=False),
) -> dict[str, object]:
    require_route_auth(current_user, "delete_report")
    report = _load_report(current_user, arkana_id)
    if not current_user.check_user_permissions("admin"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin role required")

    session_manager = ArkanaSessionManager()
    deleted_sessions = session_manager.delete_object_sessions(arkana_id)
    deleted_workspaces = session_manager.delete_object_workspaces(arkana_id)
    _delete_arkana_object(int(report.arkana_id))
    return with_help(
        {
            "status": "deleted",
            "arkana_object_id": arkana_id,
            "deleted_sessions": deleted_sessions,
            "deleted_workspaces": deleted_workspaces,
        },
        help_enabled=help,
        help_payload=build_help(
            endpoint="/report/{arkana_id}",
            method="DELETE",
            description="Deletes a report, all assigned cells, related containers and workspaces.",
            path_parameters={"arkana_id": "The report object id."},
            query_parameters={"help": "Optional. If true, appends endpoint documentation to the response."},
            returns="JSON object with deletion summary.",
        ),
    )


@router.post("/report/{arkana_id}/cell/")
def create_report_cell(
    arkana_id: int,
    request: ReportCellRequest,
    index: int | None = Query(default=None, ge=1),
    current_user: ArkanaUser = Depends(get_current_user),
    help: bool = Query(default=False),
) -> dict[str, object]:
    require_route_auth(current_user, "create_report_cell")
    report = _load_report(current_user, arkana_id)
    payload = request.model_dump(exclude_none=True)

    if index is None:
        report.append_cell(
            cell_type=str(payload.pop("cell_type", "text")),
            payload=payload,
            taggs=payload.pop("taggs", None),
        )
    else:
        report.add_cell(index=index, cell=payload)

    report.save()
    cells = report.cells or []
    if not cells:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Cell could not be created")
    created_cell = cells[-1] if index is None else cells[index - 1]
    return with_help(
        _normalize_cell_for_api(arkana_id, report.get_cell(created_cell.get("cell_key")) or created_cell),
        help_enabled=help,
        help_payload=build_help(
            endpoint="/report/{arkana_id}/cell/",
            method="POST",
            description="Creates a new top-level cell. If index is set, insertion uses the visible top-level order and ignores dependent cells.",
            path_parameters={"arkana_id": "The report object id."},
            query_parameters={
                "index": "Optional insertion position for the top-level cell list.",
                "help": "Optional. If true, appends endpoint documentation to the response.",
            },
            body="ReportCellRequest JSON body.",
            returns="JSON object for the created cell.",
        ),
    )


@router.post("/report/{arkana_id}/run")
def run_report_cells(
    arkana_id: int,
    save: bool = Query(default=True),
    current_user: ArkanaUser = Depends(get_current_user),
    help: bool = Query(default=False),
) -> dict[str, object]:
    require_route_auth(current_user, "run_report_cells")
    report = _load_report(current_user, arkana_id)
    try:
        results = report.run_all_cells(save_result=save)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    normalized_results: list[dict[str, object]] = []
    for result in results:
        if isinstance(result, dict) and isinstance(result.get("results"), list):
            normalized_results.append(
                {
                    **result,
                    "results": [
                        _normalize_cell_for_api(arkana_id, item) if isinstance(item, dict) else item
                        for item in result["results"]
                    ],
                }
            )
        else:
            normalized_results.append(result)
    return with_help(
        {"arkana_object_id": arkana_id, "save_result": save, "results": normalized_results},
        help_enabled=help,
        help_payload=build_help(
            endpoint="/report/{arkana_id}/run",
            method="POST",
            description="Runs all executable code cells in the report.",
            path_parameters={"arkana_id": "The report object id."},
            query_parameters={
                "save": "Optional. If true, persists result cells.",
                "help": "Optional. If true, appends endpoint documentation to the response.",
            },
            returns="JSON object with the run results for each executed cell.",
        ),
    )


def _run_report_cell(
    arkana_id: int,
    cell_identifier: str,
    save: bool,
    current_user: ArkanaUser = Depends(get_current_user),
    help: bool = False,
) -> dict[str, object]:
    report = _load_report(current_user, arkana_id)
    try:
        results = report.run_cell(cell_identifier, save_result=save)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    return with_help(
        {
            "arkana_object_id": arkana_id,
            "cell": cell_identifier,
            "save_result": save,
            "results": [_normalize_cell_for_api(arkana_id, item) if isinstance(item, dict) else item for item in results],
        },
        help_enabled=help,
        help_payload=build_help(
            endpoint="/report/{arkana_id}/cell/{cell_identifier}/run",
            method="GET" if not save else "POST",
            description="Runs a single executable cell. String identifiers use cell_key. Numeric identifiers use the visible top-level index.",
            path_parameters={
                "arkana_id": "The report object id.",
                "cell_identifier": "A top-level index or cell_key.",
            },
            query_parameters={
                "save": "POST only. If true, persists result cells.",
                "help": "Optional. If true, appends endpoint documentation to the response.",
            },
            returns="JSON object with the produced result cells.",
        ),
    )


@router.get("/report/{arkana_id}/cell/{cell_identifier}/run")
@router.get("/report/{arkana_id}/cell/{cell_identifier}run")
def get_run_report_cell(
    arkana_id: int,
    cell_identifier: str,
    current_user: ArkanaUser = Depends(get_current_user),
    help: bool = Query(default=False),
) -> dict[str, object]:
    require_route_auth(current_user, "get_run_report_cell")
    return _run_report_cell(arkana_id, cell_identifier, False, current_user, help)


@router.post("/report/{arkana_id}/cell/{cell_identifier}/run")
@router.post("/report/{arkana_id}/cell/{cell_identifier}run")
def post_run_report_cell(
    arkana_id: int,
    cell_identifier: str,
    save: bool = Query(default=True),
    current_user: ArkanaUser = Depends(get_current_user),
    help: bool = Query(default=False),
) -> dict[str, object]:
    require_route_auth(current_user, "post_run_report_cell")
    return _run_report_cell(arkana_id, cell_identifier, save, current_user, help)
