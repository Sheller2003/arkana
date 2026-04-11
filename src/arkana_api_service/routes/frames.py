from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from src.arkana_auth.user_object import ArkanaUser
from src.arkana_api_service.dependencies import get_current_user, get_main_db
from src.arkana_mdd_db.frame_executor import FrameExecutionError, FrameExecutor
from src.arkana_mdd_db.main_db import ArkanaMainDB
from src.arkana_mdd_db.models import FrameExecuteRequest, FrameExecuteResponse

router = APIRouter(tags=["frames"])


@router.post("/frames/execute", response_model=FrameExecuteResponse, status_code=status.HTTP_200_OK)
def execute_frame(
    request: FrameExecuteRequest,
    _: ArkanaUser = Depends(get_current_user),
    main_db: ArkanaMainDB = Depends(get_main_db),
) -> FrameExecuteResponse:
    executor = FrameExecutor(main_db)
    try:
        result = executor.execute(
            frame=request.frame,
            input_parameters=request.input_parameters,
            referenced_frames=request.referenced_frames,
        )
    except FrameExecutionError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return FrameExecuteResponse(frame_id=request.frame.get("frame_id"), result=result)
