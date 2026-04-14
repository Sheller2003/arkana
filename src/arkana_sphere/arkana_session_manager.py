from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Any

from src.arkana_sphere.arkana_python_sandbox_session import ArkanaPythonSandboxSession
from src.arkana_sphere.arkana_r_session import ArkanaRSession

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SESSIONS_ROOT_FOLDER = "arkana_spheres"


def _resolve_sessions_root() -> Path:
    configured = os.getenv("ARKANA_SESSIONS_ROOT")
    if configured:
        return Path(configured)
    return PROJECT_ROOT / SESSIONS_ROOT_FOLDER


class ArkanaSessionManager:
    SESSION_TYPES = {
        "python": ArkanaPythonSandboxSession,
        "py": ArkanaPythonSandboxSession,
        "r": ArkanaRSession,
    }

    def __init__(self):
        self.base_path = _resolve_sessions_root()
        self.base_path.mkdir(parents=True, exist_ok=True)

    def create_session(
        self,
        arkana_object_id,
        user_object,
        runtime_type: str = "py",
        lifetime_seconds: int = 30 * 60,
    ):
        session_cls = self._resolve_session_class(runtime_type)
        session = session_cls(
            user_object=user_object,
            arkana_object_id=arkana_object_id,
            lifetime_seconds=lifetime_seconds,
        )
        session.start_session()
        return session

    def get_session(self, arkana_object_id, user_object, runtime_type: str):
        session_cls = self._resolve_session_class(runtime_type)
        existing_session = self._find_session_metadata(
            arkana_object_id=str(arkana_object_id),
            user_id=str(user_object.user_id),
            runtime_type=self._normalize_runtime_type(runtime_type),
        )
        if existing_session:
            session = session_cls(
                user_object=user_object,
                arkana_object_id=arkana_object_id,
                session_id=str(existing_session["session_id"]),
            )
            if session.get_session_state().get("exists"):
                return session
        return self.create_session(
            arkana_object_id=arkana_object_id,
            user_object=user_object,
            runtime_type=runtime_type,
        )

    def delete_session(self, arkana_object_id, user_object, runtime_type: str) -> bool:
        session = self.get_session(
            arkana_object_id=arkana_object_id,
            user_object=user_object,
            runtime_type=runtime_type,
        )
        return session.delete_session()

    def extend_session(self, arkana_object_id, user_object, runtime_type: str, lifetime_seconds: int):
        session = self.get_session(
            arkana_object_id=arkana_object_id,
            user_object=user_object,
            runtime_type=runtime_type,
        )
        return session.keep_alive(lifetime_seconds)

    def list_sessions(self) -> list[dict[str, Any]]:
        sessions: list[dict[str, Any]] = []
        for metadata_path in sorted(self.base_path.glob("*/metadata.json")):
            try:
                session_data = self._read_metadata(metadata_path)
            except Exception:
                continue
            sessions.append(session_data)
        return sessions

    def get_object_sessions(self, arkana_object_id, user_object=None) -> list[dict[str, Any]]:
        sessions: list[dict[str, Any]] = []
        expected_object_id = str(arkana_object_id)
        expected_user_id = str(user_object.user_id) if user_object is not None else None

        for session in self.list_sessions():
            if str(session.get("arkana_object_id")) != expected_object_id:
                continue
            if expected_user_id is not None and str(session.get("user_id")) != expected_user_id:
                continue
            sessions.append(session)
        return sessions

    def list_workspaces(self) -> list[dict[str, str]]:
        workspace_root = self.base_path / "workspaces"
        if not workspace_root.exists():
            return []

        workspaces: list[dict[str, str]] = []
        for workspace_path in sorted(workspace_root.iterdir()):
            if not workspace_path.is_dir():
                continue
            workspaces.append(
                {
                    "workspace_key": workspace_path.name,
                    "workspace_path": str(workspace_path),
                }
            )
        return workspaces

    def get_session_files(
        self,
        arkana_object_id,
        user_object,
        endings: tuple[str, ...] = (".csv", ".txt", ".png"),
    ) -> list[dict[str, str]]:
        normalized_endings = tuple(ending.lower() for ending in endings)
        files: list[dict[str, str]] = []
        workspace_path = self.get_workspace_path(arkana_object_id=arkana_object_id, user_object=user_object)
        if not workspace_path.exists():
            return files

        session_map = self._get_workspace_session_map(arkana_object_id=arkana_object_id, user_object=user_object)
        for path in sorted(workspace_path.rglob("*")):
            if not path.is_file():
                continue
            if path.suffix.lower() not in normalized_endings:
                continue
            files.append(
                {
                    "session_id": session_map.get("session_id", ""),
                    "runtime_type": session_map.get("runtime_type", ""),
                    "file_name": path.name,
                    "relative_path": str(path.relative_to(workspace_path)),
                    "absolute_path": str(path),
                }
            )

        return files

    def get_session_file(
        self,
        arkana_object_id,
        user_object,
        file_name: str,
        endings: tuple[str, ...] = (".csv", ".txt", ".png"),
    ) -> dict[str, str] | None:
        for file_info in reversed(
            self.get_session_files(
                arkana_object_id=arkana_object_id,
                user_object=user_object,
                endings=endings,
            )
        ):
            if file_info["file_name"] == file_name:
                return file_info
        return None

    def get_workspace_path(self, arkana_object_id, user_object) -> Path:
        workspace_root = self.base_path / "workspaces"
        return workspace_root / self._workspace_key(arkana_object_id=arkana_object_id)

    def cleanup_expired_sessions(self) -> list[str]:
        removed: list[str] = []
        for session in self.list_sessions():
            runtime_type = str(session.get("runtime_type") or "py")
            session_id = str(session.get("session_id") or "")
            if not session_id:
                continue
            session_cls = self._resolve_session_class(runtime_type)
            user_object = _SessionUserProxy(str(session.get("user_id") or ""))
            session_obj = session_cls(
                user_object=user_object,
                arkana_object_id=session.get("arkana_object_id"),
                session_id=session_id,
            )
            if session_obj.get_session_state().get("expired"):
                session_obj.delete_session()
                removed.append(session_id)
        return removed

    def delete_object_sessions(self, arkana_object_id) -> list[str]:
        removed: list[str] = []
        for session in self.list_sessions():
            if str(session.get("arkana_object_id")) != str(arkana_object_id):
                continue
            runtime_type = str(session.get("runtime_type") or "py")
            session_id = str(session.get("session_id") or "")
            user_object = _SessionUserProxy(str(session.get("user_id") or ""))
            session_cls = self._resolve_session_class(runtime_type)
            session_obj = session_cls(
                user_object=user_object,
                arkana_object_id=arkana_object_id,
                session_id=session_id,
            )
            session_obj.delete_session()
            removed.append(session_id)
        return removed

    def restart_object_sessions(self, arkana_object_id, user_object) -> list[dict[str, Any]]:
        current_sessions = self.get_object_sessions(arkana_object_id, user_object=user_object)
        runtime_types: list[str] = []
        for session in current_sessions:
            runtime_type = self._normalize_runtime_type(str(session.get("runtime_type") or "py"))
            if runtime_type not in runtime_types:
                runtime_types.append(runtime_type)

        restarted: list[dict[str, Any]] = []
        if not runtime_types:
            return restarted

        self.delete_object_sessions_for_user(arkana_object_id, user_object=user_object)
        for runtime_type in runtime_types:
            session = self.create_session(
                arkana_object_id=arkana_object_id,
                user_object=user_object,
                runtime_type=runtime_type,
            )
            restarted.append(session.get_session_state())
        return restarted

    def delete_object_sessions_for_user(self, arkana_object_id, user_object) -> list[str]:
        removed: list[str] = []
        expected_user_id = str(user_object.user_id)
        for session in self.list_sessions():
            if str(session.get("arkana_object_id")) != str(arkana_object_id):
                continue
            if str(session.get("user_id")) != expected_user_id:
                continue
            runtime_type = str(session.get("runtime_type") or "py")
            session_id = str(session.get("session_id") or "")
            session_cls = self._resolve_session_class(runtime_type)
            session_obj = session_cls(
                user_object=user_object,
                arkana_object_id=arkana_object_id,
                session_id=session_id,
            )
            session_obj.delete_session()
            removed.append(session_id)
        return removed

    def delete_object_workspaces(self, arkana_object_id) -> list[str]:
        removed: list[str] = []
        workspace_root = self.base_path / "workspaces"
        if not workspace_root.exists():
            return removed

        expected_name = self._workspace_key(arkana_object_id=arkana_object_id)
        for workspace_path in sorted(workspace_root.iterdir()):
            if not workspace_path.is_dir():
                continue
            if workspace_path.name != expected_name:
                continue
            shutil.rmtree(workspace_path, ignore_errors=True)
            removed.append(str(workspace_path))
        return removed

    def _resolve_session_class(self, session_type: str):
        normalized = self._normalize_runtime_type(session_type)
        if normalized not in self.SESSION_TYPES:
            raise ValueError(f"Unsupported session type: {session_type}")
        return self.SESSION_TYPES[normalized]

    def _normalize_runtime_type(self, runtime_type: str) -> str:
        normalized = str(runtime_type).strip().lower()
        if normalized == "python":
            return "py"
        return normalized

    def _find_session_metadata(self, arkana_object_id: str, user_id: str, runtime_type: str) -> dict[str, Any] | None:
        for session_data in self.list_sessions():
            if str(session_data.get("arkana_object_id")) != arkana_object_id:
                continue
            if str(session_data.get("user_id")) != user_id:
                continue
            if str(session_data.get("runtime_type") or "py") != runtime_type:
                continue
            return session_data
        return None

    def _read_metadata(self, metadata_path: Path) -> dict[str, Any]:
        import json

        return json.loads(metadata_path.read_text(encoding="utf-8"))

    def _slug(self, value: Any) -> str:
        text = str(value).strip().lower()
        allowed = [char if char.isalnum() else "-" for char in text]
        slug = "".join(allowed).strip("-")
        return slug or "unknown"

    def _workspace_key(self, *, arkana_object_id) -> str:
        return f"report_{self._slug(arkana_object_id)}"

    def _get_workspace_session_map(self, *, arkana_object_id, user_object) -> dict[str, str]:
        sessions = self.get_object_sessions(arkana_object_id, user_object=user_object)
        if not sessions:
            return {"session_id": "", "runtime_type": ""}
        newest = sessions[-1]
        return {
            "session_id": str(newest.get("session_id") or ""),
            "runtime_type": str(newest.get("runtime_type") or ""),
        }


class _SessionUserProxy:
    def __init__(self, user_id: str):
        self.user_id = user_id
