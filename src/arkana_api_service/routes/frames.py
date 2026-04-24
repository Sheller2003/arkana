from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status

from src.arkana_api_service.route_auth import require_route_auth
from src.arkana_auth.user_object import ArkanaUser
from src.arkana_api_service.dependencies import get_current_user, get_main_db
from src.arkana_api_service.routes.help_utils import build_help, with_help
from src.arkana_mdd_db.frame_executor import FrameExecutionError, FrameExecutor
from src.arkana_mdd_db.main_db import ArkanaMainDB
from src.arkana_mdd_db.models import FrameExecuteRequest, FrameExecuteResponse

router = APIRouter(tags=["frames"])


@router.post("/frames/execute", status_code=status.HTTP_200_OK)
def execute_frame(
    request: FrameExecuteRequest,
    current_user: ArkanaUser = Depends(get_current_user),
    main_db: ArkanaMainDB = Depends(get_main_db),
    help: bool = Query(default=False),
) -> dict[str, object]:
    require_route_auth(current_user, "execute_frame")
    executor = FrameExecutor(main_db)
    try:
        result = executor.execute(
            frame=request.frame,
            input_parameters=request.input_parameters,
            referenced_frames=request.referenced_frames,
        )
    except FrameExecutionError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return with_help(
        FrameExecuteResponse(frame_id=request.frame.get("frame_id"), result=result),
        help_enabled=help,
        help_payload=build_help(
            endpoint="/frames/execute",
            method="POST",
            description="Executes a frame definition with optional input parameters and referenced frames.",
            query_parameters={"help": "Optional. If true, appends endpoint documentation to the response."},
            body="FrameExecuteRequest JSON body.",
            returns="JSON object with frame_id and the execution result.",
        ),
    )
