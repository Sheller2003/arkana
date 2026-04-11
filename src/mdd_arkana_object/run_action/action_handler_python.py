from __future__ import annotations

from src.arkana_sphere.arkana_session_manager import ArkanaSessionManager
from src.arkana_sphere.arkana_session_run_result import ArkanaSessionRunResult
from src.mdd_arkana_object.cell_types import CellType
from src.mdd_arkana_object.run_action.action_handler_interface import ActionHandlerInterface


class ActionHandlerPython(ActionHandlerInterface):
    allowed_cell_types = [CellType.PY_CODE.value]
    runtime_type = "py"
    result_cell_type = CellType.PY_RESULT.value

    def run_action(self, cell_value: str) -> ArkanaSessionRunResult:
        session = ArkanaSessionManager().get_session(
            arkana_object_id=self.get_arkana_id(),
            user_object=self.user_object,
            runtime_type=self.runtime_type,
        )
        return session.run_command(cell_value)
