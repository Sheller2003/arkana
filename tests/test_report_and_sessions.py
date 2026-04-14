from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.arkana_sphere.arkana_session_interface import ArkanaSessionInterface
from src.mdd_arkana_object.ark_report import ArkanaReport
from src.mdd_arkana_object.cell_types import CellType
from src.mdd_arkana_object.run_action.action_handler_r import ActionHandlerR


class _DummyAccounting:
    def load_by_db(self):
        return self

    def check_for_runtime_available(self, _: int) -> bool:
        return True

    def logg_runtime(self, _: int) -> None:
        return None

    def save(self, _: object) -> None:
        return None


class _DummyUser:
    def __init__(self, user_id: str = "user-1", user_role: str = "root") -> None:
        self.user_id = user_id
        self.user_role = user_role
        self.main_db = MagicMock()

    def get_accounting_obj(self) -> _DummyAccounting:
        return _DummyAccounting()


class _DummySession(ArkanaSessionInterface):
    language = "python"
    docker_image = "python:3.11-slim"


class ArkanaReportTests(unittest.TestCase):
    def setUp(self) -> None:
        self.report = ArkanaReport(arkana_id=5, user_object=_DummyUser())
        self.report.cells = []

    def test_append_file_cell_promotes_specific_file_type(self) -> None:
        self.report.append_cell(cell_type=CellType.FILE.value, payload="data.json")

        self.assertEqual(self.report.cells[0]["cell_type"], CellType.FILE_JSON.value)
        self.assertEqual(self.report.cells[0]["content"], "data.json")

    def test_update_file_cell_promotes_specific_file_type(self) -> None:
        self.report.cells = [
            {
                "cell_id": 1,
                "order_id": 1,
                "prev_id": 0,
                "prev": 0,
                "depend_by": None,
                "cell_key": "cell_1",
                "cell_type": CellType.FILE.value,
                "taggs": None,
                "content": "old.csv",
            }
        ]

        self.report.update_cell(1, {"cell_type": CellType.FILE.value, "content": "fresh.csv"})

        self.assertEqual(self.report.cells[0]["cell_type"], CellType.FILE_CSV.value)
        self.assertEqual(self.report.cells[0]["content"], "fresh.csv")

    def test_replace_result_cells_preserves_existing_file_references(self) -> None:
        parent_cell = {
            "cell_id": 1,
            "order_id": 1,
            "prev_id": 0,
            "prev": 0,
            "depend_by": None,
            "cell_key": "py_code",
            "cell_type": CellType.PY_CODE.value,
            "content": "print('hi')",
        }
        existing_file_cell = {
            "cell_id": 2,
            "order_id": 1,
            "prev_id": 0,
            "prev": 0,
            "depend_by": 1,
            "cell_key": "py_code",
            "cell_type": CellType.FILE_JSON.value,
            "content": "result.json",
        }
        self.report.cells = [parent_cell, existing_file_cell]

        updated = self.report._replace_result_cells(
            0,
            parent_cell,
            [
                {"cell_type": CellType.PY_RESULT.value, "content": "done"},
                {"cell_type": CellType.FILE.value, "content": "result.json"},
            ],
        )

        file_cells = [cell for cell in updated if str(cell.get("cell_type")).startswith("file")]
        self.assertEqual(len(file_cells), 1)
        self.assertEqual(file_cells[0]["content"], "result.json")


class ActionHandlerRTests(unittest.TestCase):
    def test_build_r_command_loads_all_rdata_files_before_code(self) -> None:
        handler = ActionHandlerR(assigned_to_arkana_id=7, field_id=1, field_value="summary(x)", running_id=1, user_object=_DummyUser())

        with patch.object(ActionHandlerR, "_get_rdata_files", return_value=["base.RData", "extra.rdata"]):
            command = handler._build_r_command("summary(x)")

        self.assertEqual(command, 'load("base.RData")\nload("extra.rdata")\nsummary(x)')


class ArkanaSessionInterfaceTests(unittest.TestCase):
    def test_workspace_key_is_report_scoped(self) -> None:
        session = _DummySession(user_object=_DummyUser("user-9"), arkana_object_id=42)

        self.assertEqual(session.workspace_key, "report_42")

    def test_create_container_uses_shared_report_workspace(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir, patch.dict(os.environ, {"ARKANA_SESSIONS_ROOT": tmp_dir, "ARKANA_DOCKER_BIN": "/usr/bin/docker"}, clear=False):
            session = _DummySession(user_object=_DummyUser("user-9"), arkana_object_id=42)
            with patch.object(_DummySession, "_ensure_image_available") as ensure_image, patch(
                "src.arkana_sphere.arkana_session_interface.subprocess.run",
                return_value=SimpleNamespace(returncode=0, stdout="container-id\n", stderr=""),
            ) as run_subprocess:
                result = session.create_container()

        self.assertEqual(result, "container-id")
        ensure_image.assert_called_once_with()
        command = run_subprocess.call_args[0][0]
        self.assertIn(f"{Path(tmp_dir) / 'workspaces' / 'report_42'}:/workspace", command)
        self.assertIn("--name", command)
        self.assertIn(session.container_name, command)

    def test_run_command_executes_and_reports_new_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir, patch.dict(os.environ, {"ARKANA_SESSIONS_ROOT": tmp_dir, "ARKANA_DOCKER_BIN": "/usr/bin/docker"}, clear=False):
            session = _DummySession(user_object=_DummyUser("user-9"), arkana_object_id=42, session_id="python-42-test")
            session.workspace_path.mkdir(parents=True, exist_ok=True)

            def _fake_subprocess_run(command, capture_output, text, check):
                (session.workspace_path / "result.csv").write_text("a,b\n1,2\n", encoding="utf-8")
                return SimpleNamespace(returncode=0, stdout="ok\n", stderr="")

            with patch.object(_DummySession, "_cleanup_if_expired"), patch.object(_DummySession, "_ensure_session_ready"), patch.object(
                _DummySession,
                "_ensure_runtime_available",
            ), patch.object(_DummySession, "logg_usage") as logg_usage, patch(
                "src.arkana_sphere.arkana_session_interface.subprocess.run",
                side_effect=_fake_subprocess_run,
            ):
                result = session.run_command("print('ok')")

        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "ok\n")
        self.assertEqual(result.session_files, ["result.csv"])
        self.assertEqual(result.command, "print('ok')")
        logg_usage.assert_called_once()


if __name__ == "__main__":
    unittest.main()
