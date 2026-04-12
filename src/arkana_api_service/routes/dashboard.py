from __future__ import annotations

import os

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse, HTMLResponse, PlainTextResponse, RedirectResponse

from src.arkana_api_service.dependencies import get_current_user
from src.arkana_api_service.routes.help_utils import build_help, with_help
from src.arkana_auth.user_object import ArkanaUser
from src.arkana_mdd_db.config import load_env
from src.arkana_mdd_db.models import DashboardCellRequest, DashboardCreateRequest
from src.arkana_sphere.arkana_session_manager import ArkanaSessionManager
from src.mdd_arkana_object.ark_report import ArkanaReport
from src.mdd_arkana_object.arkana_object_manager import ArkanaObjectManager

router = APIRouter(tags=["report"])


def _delete_arkana_object(arkana_id: int) -> None:
    _, cursor = ArkanaReport()._ensure_cursor()
    cursor.execute("DELETE FROM arkana_object WHERE arkana_id = %s", (int(arkana_id),))
    ArkanaReport._commit()


def _get_root_path() -> str:
    load_env()
    return os.getenv("ROOT_PATH", "http://127.0.0.1:8000").rstrip("/")


def _normalize_cell_for_api(arkana_id: int, cell: dict[str, object]) -> dict[str, object]:
    normalized = dict(cell)
    if str(normalized.get("cell_type") or "").lower() == "file":
        content = str(normalized.get("content") or "").strip()
        if content and not content.startswith("http://") and not content.startswith("https://"):
            normalized["content"] = f"{_get_root_path()}/report/{arkana_id}/files/{content}"
    child_cells = normalized.get("cells")
    if isinstance(child_cells, list):
        normalized["cells"] = [
            _normalize_cell_for_api(arkana_id, child)
            for child in child_cells
            if isinstance(child, dict)
        ]
    return normalized


@router.get("/report/{arkana_id}")
def get_dashboard(
    arkana_id: int,
    current_user: ArkanaUser = Depends(get_current_user),
    help: bool = Query(default=False),
) -> dict[str, object]:
    manager = ArkanaObjectManager(current_user)
    try:
        dashboard = manager.get_object(arkana_id).load()
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
        _normalize_cell_for_api(arkana_id, dashboard.to_json()),
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
def create_dashboard(
    request: DashboardCreateRequest,
    current_user: ArkanaUser = Depends(get_current_user),
    help: bool = Query(default=False),
) -> dict[str, object]:
    auth_group = int(request.auth_group or 1)
    if not current_user.check_user_group_allowed(auth_group):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Arkana object not allowed")

    board = ArkanaReport(
        arkana_type="report",
        auth_group=auth_group,
        object_key=request.object_key,
        description=request.description,
        arkana_group=request.arkana_group if request.arkana_group is not None else auth_group,
        user_object=current_user,
    )
    board.cells = []
    for cell_request in request.cells:
        payload = cell_request.model_dump(exclude_none=True)
        board.append_cell(
            cell_type=str(payload.pop("cell_type", "text")),
            payload=payload.get("content"),
            taggs=payload.get("taggs"),
        )
        if board.cells:
            latest = board.cells[-1]
            if payload.get("cell_key") is not None:
                latest["cell_key"] = payload["cell_key"]
    board.save()
    return with_help(
        _normalize_cell_for_api(int(board.arkana_id), board.to_json()),
        help_enabled=help,
        help_payload=build_help(
            endpoint="/report",
            method="POST",
            description="Creates a new report and optionally seeds it with initial cells.",
            query_parameters={"help": "Optional. If true, appends endpoint documentation to the response."},
            body="DashboardCreateRequest JSON body.",
            returns="JSON object with the created report.",
        ),
    )


def _load_dashboard(current_user: ArkanaUser, arkana_id: int) -> ArkanaReport:
    manager = ArkanaObjectManager(current_user)
    try:
        dashboard = manager.get_object(arkana_id).load()
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

    if not isinstance(dashboard, ArkanaReport):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Object is not a report")
    return dashboard


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


def _cell_get_response(cell: dict[str, object]):
    cell_type = str(cell.get("cell_type") or "").lower()
    content = cell.get("content")

    if cell_type == "file":
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
def get_dashboard_cell(
    arkana_id: int,
    cell_identifier: str,
    cell_id: int | None = Query(default=None, ge=1),
    current_user: ArkanaUser = Depends(get_current_user),
    help: bool = Query(default=False),
) -> dict[str, object]:
    dashboard = _load_dashboard(current_user, arkana_id)
    if cell_identifier == "get" and cell_id is not None:
        cell = dashboard.get_cell_by_id(cell_id)
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
    cell = dashboard.get_cell_by_id(cell_id) if cell_id is not None else dashboard.get_cell(cell_identifier)
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
def get_dashboard_cell_by_id(
    arkana_id: int,
    cell_id: int = Query(..., ge=1),
    current_user: ArkanaUser = Depends(get_current_user),
    help: bool = Query(default=False),
) -> dict[str, object]:
    dashboard = _load_dashboard(current_user, arkana_id)
    cell = dashboard.get_cell_by_id(cell_id)
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
def get_dashboard_cell_content_by_id(
    arkana_id: int,
    cell_id: int = Query(..., ge=1),
    current_user: ArkanaUser = Depends(get_current_user),
    help: bool = Query(default=False),
):
    dashboard = _load_dashboard(current_user, arkana_id)
    cell = dashboard.get_cell_by_id(cell_id)
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
def get_dashboard_cell_content(
    arkana_id: int,
    cell_identifier: str,
    current_user: ArkanaUser = Depends(get_current_user),
    help: bool = Query(default=False),
):
    dashboard = _load_dashboard(current_user, arkana_id)
    cell = dashboard.get_cell(cell_identifier)
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
def get_dashboard_files(
    arkana_id: int,
    current_user: ArkanaUser = Depends(get_current_user),
    help: bool = Query(default=False),
) -> dict[str, object]:
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
def get_dashboard_file(
    arkana_id: int,
    file_name: str,
    current_user: ArkanaUser = Depends(get_current_user),
    help: bool = Query(default=False),
):
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


@router.put("/report/{arkana_id}/cell/{cell_identifier}")
def update_dashboard_cell(
    arkana_id: int,
    cell_identifier: str,
    request: DashboardCellRequest,
    current_user: ArkanaUser = Depends(get_current_user),
    help: bool = Query(default=False),
) -> dict[str, object]:
    dashboard = _load_dashboard(current_user, arkana_id)
    payload = request.model_dump(exclude_none=True)
    dashboard.update_cell(cell_identifier, payload)
    cell = dashboard.get_cell(cell_identifier)
    if cell is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cell not found")
    dashboard.save()
    result_cell = dashboard.get_cell(cell_identifier) or cell
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
            body="DashboardCellRequest JSON body.",
            returns="JSON object for the updated cell.",
        ),
    )


@router.delete("/report/{arkana_id}/cell/{cell_identifier}")
def delete_dashboard_cell(
    arkana_id: int,
    cell_identifier: str,
    current_user: ArkanaUser = Depends(get_current_user),
    help: bool = Query(default=False),
) -> dict[str, object]:
    dashboard = _load_dashboard(current_user, arkana_id)
    cell = dashboard.get_cell(cell_identifier)
    if cell is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cell not found")
    dashboard.delete_cell(cell_identifier).save()
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


@router.delete("/report/{arkana_id}")
def delete_dashboard(
    arkana_id: int,
    current_user: ArkanaUser = Depends(get_current_user),
    help: bool = Query(default=False),
) -> dict[str, object]:
    dashboard = _load_dashboard(current_user, arkana_id)
    if not current_user.check_user_permissions("admin"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin role required")

    session_manager = ArkanaSessionManager()
    deleted_sessions = session_manager.delete_object_sessions(arkana_id)
    deleted_workspaces = session_manager.delete_object_workspaces(arkana_id)
    _delete_arkana_object(int(dashboard.arkana_id))
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
def create_dashboard_cell(
    arkana_id: int,
    request: DashboardCellRequest,
    index: int | None = Query(default=None, ge=1),
    current_user: ArkanaUser = Depends(get_current_user),
    help: bool = Query(default=False),
) -> dict[str, object]:
    dashboard = _load_dashboard(current_user, arkana_id)
    payload = request.model_dump(exclude_none=True)

    if index is None:
        dashboard.append_cell(
            cell_type=str(payload.pop("cell_type", "text")),
            payload=payload,
            taggs=payload.pop("taggs", None),
        )
    else:
        dashboard.add_cell(index=index, cell=payload)

    dashboard.save()
    cells = dashboard.cells or []
    if not cells:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Cell could not be created")
    created_cell = cells[-1] if index is None else cells[index - 1]
    return with_help(
        _normalize_cell_for_api(arkana_id, dashboard.get_cell(created_cell.get("cell_key")) or created_cell),
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
            body="DashboardCellRequest JSON body.",
            returns="JSON object for the created cell.",
        ),
    )


@router.post("/report/{arkana_id}/run")
def run_dashboard_cells(
    arkana_id: int,
    save: bool = Query(default=True),
    current_user: ArkanaUser = Depends(get_current_user),
    help: bool = Query(default=False),
) -> dict[str, object]:
    dashboard = _load_dashboard(current_user, arkana_id)
    try:
        results = dashboard.run_all_cells(save_result=save)
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


def _run_dashboard_cell(
    arkana_id: int,
    cell_identifier: str,
    save: bool,
    current_user: ArkanaUser = Depends(get_current_user),
    help: bool = False,
) -> dict[str, object]:
    dashboard = _load_dashboard(current_user, arkana_id)
    try:
        results = dashboard.run_cell(cell_identifier, save_result=save)
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
def get_run_dashboard_cell(
    arkana_id: int,
    cell_identifier: str,
    current_user: ArkanaUser = Depends(get_current_user),
    help: bool = Query(default=False),
) -> dict[str, object]:
    return _run_dashboard_cell(arkana_id, cell_identifier, False, current_user, help)


@router.post("/report/{arkana_id}/cell/{cell_identifier}/run")
@router.post("/report/{arkana_id}/cell/{cell_identifier}run")
def post_run_dashboard_cell(
    arkana_id: int,
    cell_identifier: str,
    save: bool = Query(default=True),
    current_user: ArkanaUser = Depends(get_current_user),
    help: bool = Query(default=False),
) -> dict[str, object]:
    return _run_dashboard_cell(arkana_id, cell_identifier, save, current_user, help)
