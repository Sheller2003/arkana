from __future__ import annotations

import time
from typing import Any

from src.arkana_sphere.arkana_session_run_result import ArkanaSessionRunResult
from src.mdd_arkana_object.cell_types import CellType


class ActionHandlerInterface:
    allowed_cell_types: list[str] = []
    runtime_type = ""
    result_cell_type = CellType.TEXT.value
    _action_log: list[dict[str, Any]] = []

    def __init__(self, assigned_to_arkana_id, field_id: str | int, field_value: str, running_id: str | int, user_object):
        self._arkana_id = int(assigned_to_arkana_id)
        self.field_id = field_id
        self.field_value = field_value
        self.running_id = running_id
        self.user_object = user_object

    def _set_allowed_cell_types(self, allowed_cell_types: list[str]):
        self.allowed_cell_types = list(allowed_cell_types)

    def check_cell_type(self, cell_type: str) -> bool:
        return cell_type in self.allowed_cell_types

    def run_action(self, cell_value: str) -> ArkanaSessionRunResult:
        raise NotImplementedError

    def execute(self) -> list[dict[str, Any]]:
        result = self.run_action(self.field_value)
        self.log_action(self.field_value, result)
        return self._result_to_cells(result)

    def log_action(self, cell_value: str, result: ArkanaSessionRunResult | None = None) -> str:
        entry = {
            "timestamp": time.time(),
            "arkana_id": self._arkana_id,
            "field_id": self.field_id,
            "running_id": self.running_id,
            "cell_value": cell_value,
            "returncode": None if result is None else result.returncode,
        }
        self._action_log.append(entry)
        return str(entry["timestamp"])

    def get_arkana_id(self) -> int:
        return self._arkana_id

    def get_result_cells(self) -> list[dict[str, Any]]:
        return self.execute()

    def _result_to_cells(self, result: ArkanaSessionRunResult) -> list[dict[str, Any]]:
        cells: list[dict[str, Any]] = []
        output_parts: list[str] = []
        if result.stdout:
            output_parts.append(result.stdout.rstrip())
        if result.stderr:
            output_parts.append(result.stderr.rstrip())
        if not output_parts:
            output_parts.append(f"returncode={result.returncode}")

        cells.append(
            {
                "cell_id": -1,
                "cell_type": self.result_cell_type,
                "content": "\n\n".join(part for part in output_parts if part),
                "runtime_seconds": result.runtime_seconds,
                "returncode": result.returncode,
                "session_id": result.session_id,
            }
        )

        for session_file in result.get_session_files():
            cells.append(
                {
                    "cell_id": -1,
                    "cell_type": CellType.FILE.value,
                    "content": session_file,
                    "session_id": result.session_id,
                }
            )
        return cells


class UnsupportedActionHandler(ActionHandlerInterface):
    result_cell_type = CellType.TEXT.value

    def run_action(self, cell_value: str) -> ArkanaSessionRunResult:
        message = f"Unsupported action cell_type for field_id={self.field_id}"
        return ArkanaSessionRunResult(
            session_id="",
            command=cell_value,
            returncode=1,
            stderr=message,
            runtime_seconds=0,
        )


def build_action_handler(
    *,
    assigned_to_arkana_id,
    field_id: str | int,
    field_value: str,
    running_id: str | int,
    user_object,
    cell_type: str,
) -> ActionHandlerInterface:
    from src.mdd_arkana_object.run_action.action_handler_python import ActionHandlerPython
    from src.mdd_arkana_object.run_action.action_handler_r import ActionHandlerR

    normalized = str(cell_type or "").strip().lower()
    if normalized == CellType.PY_CODE.value:
        return ActionHandlerPython(assigned_to_arkana_id, field_id, field_value, running_id, user_object)
    if normalized == CellType.R_CODE.value:
        return ActionHandlerR(assigned_to_arkana_id, field_id, field_value, running_id, user_object)
    return UnsupportedActionHandler(assigned_to_arkana_id, field_id, field_value, running_id, user_object)






