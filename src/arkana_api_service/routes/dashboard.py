from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse

from src.arkana_api_service.dependencies import get_current_user
from src.arkana_auth.user_object import ArkanaUser
from src.arkana_mdd_db.models import DashboardCellRequest
from src.arkana_sphere.arkana_session_manager import ArkanaSessionManager
from src.mdd_arkana_object.ark_board import ArkBoard
from src.mdd_arkana_object.arkana_object_manager import ArkanaObjectManager

router = APIRouter(tags=["dashboard"])


@router.get("/dashboard/{arkana_id}")
def get_dashboard(
    arkana_id: int,
    current_user: ArkanaUser = Depends(get_current_user),
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
    return dashboard.to_json()


def _load_dashboard(current_user: ArkanaUser, arkana_id: int) -> ArkBoard:
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

    if not isinstance(dashboard, ArkBoard):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Object is not a dashboard")
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


@router.get("/dashboard/{arkana_id}/cell/{cell_identifier}")
def get_dashboard_cell(
    arkana_id: int,
    cell_identifier: str,
    current_user: ArkanaUser = Depends(get_current_user),
) -> dict[str, object]:
    dashboard = _load_dashboard(current_user, arkana_id)
    cell = dashboard.get_cell(cell_identifier)
    if cell is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cell not found")
    return cell


@router.get("/dashboard/{arkana_id}/files")
def get_dashboard_files(
    arkana_id: int,
    current_user: ArkanaUser = Depends(get_current_user),
) -> dict[str, object]:
    _ensure_object_group_access(current_user, arkana_id)
    session_manager = ArkanaSessionManager()
    files = session_manager.get_session_files(
        arkana_object_id=arkana_id,
        user_object=current_user,
        endings=(".csv", ".txt", ".png"),
    )
    return {"arkana_object_id": arkana_id, "files": files}


@router.get("/dashboard/{arkana_id}/files/{file_name}")
def get_dashboard_file(
    arkana_id: int,
    file_name: str,
    current_user: ArkanaUser = Depends(get_current_user),
) -> FileResponse:
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
    return FileResponse(path=file_info["absolute_path"], filename=file_info["file_name"])


@router.put("/dashboard/{arkana_id}/cell/{cell_identifier}")
def update_dashboard_cell(
    arkana_id: int,
    cell_identifier: str,
    request: DashboardCellRequest,
    current_user: ArkanaUser = Depends(get_current_user),
) -> dict[str, object]:
    dashboard = _load_dashboard(current_user, arkana_id)
    payload = request.model_dump(exclude_none=True)
    dashboard.update_cell(cell_identifier, payload)
    cell = dashboard.get_cell(cell_identifier)
    if cell is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cell not found")
    dashboard.save()
    return dashboard.get_cell(cell_identifier) or cell


@router.delete("/dashboard/{arkana_id}/cell/{cell_identifier}")
def delete_dashboard_cell(
    arkana_id: int,
    cell_identifier: str,
    current_user: ArkanaUser = Depends(get_current_user),
) -> dict[str, object]:
    dashboard = _load_dashboard(current_user, arkana_id)
    cell = dashboard.get_cell(cell_identifier)
    if cell is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cell not found")
    dashboard.delete_cell(cell_identifier).save()
    return {"status": "deleted", "cell": cell}


@router.post("/dashboard/{arkana_id}/cell/")
def create_dashboard_cell(
    arkana_id: int,
    request: DashboardCellRequest,
    index: int | None = Query(default=None, ge=1),
    current_user: ArkanaUser = Depends(get_current_user),
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
    return created_cell
