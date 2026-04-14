from __future__ import annotations

import json

from src.arkana_sphere.arkana_session_manager import ArkanaSessionManager
from src.arkana_sphere.arkana_session_run_result import ArkanaSessionRunResult
from src.mdd_arkana_object.cell_types import CellType
from src.mdd_arkana_object.run_action.action_handler_interface import ActionHandlerInterface


class ActionHandlerR(ActionHandlerInterface):
    allowed_cell_types = [CellType.R_CODE.value]
    runtime_type = "r"
    result_cell_type = CellType.R_RESULT.value

    def run_action(self, cell_value: str) -> ArkanaSessionRunResult:
        session = ArkanaSessionManager().get_session(
            arkana_object_id=self.get_arkana_id(),
            user_object=self.user_object,
            runtime_type=self.runtime_type,
        )
        return session.run_command(self._build_r_command(cell_value))

    def _build_r_command(self, cell_value: str) -> str:
        load_commands: list[str] = []
        for file_name in self._get_rdata_files():
            load_commands.append(f"load({json.dumps(file_name)})")
        if not load_commands:
            return cell_value
        return "\n".join([*load_commands, cell_value])

    def _get_rdata_files(self) -> list[str]:
        from src.mdd_arkana_object.ark_report import ArkanaReport

        report = ArkanaReport(arkana_id=self.get_arkana_id(), user_object=self.user_object).load()
        rdata_files: list[str] = []
        for cell in report.cells or []:
            if str(cell.get("cell_type") or "").lower() != CellType.RDATA.value:
                continue
            file_name = str(cell.get("content") or "").strip().split("/")[-1]
            if not file_name:
                continue
            rdata_files.append(file_name)
        return rdata_files
