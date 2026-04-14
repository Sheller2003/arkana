from __future__ import annotations

import json
import math
import os
import shutil
import subprocess
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from src.arkana_sphere.arkana_session_run_result import ArkanaSessionRunResult


DEFAULT_SESSION_LIFETIME_SECONDS = 30 * 60
CONTAINER_WORKDIR = "/workspace"
SESSIONS_ROOT_FOLDER = "arkana_spheres"
PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _resolve_sessions_root() -> Path:
    configured = os.getenv("ARKANA_SESSIONS_ROOT")
    if configured:
        return Path(configured)
    return PROJECT_ROOT / SESSIONS_ROOT_FOLDER


class ArkanaSessionInterface:
    language = "generic"
    docker_image = ""
    container_command = ["tail", "-f", "/dev/null"]

    def __init__(
        self,
        user_object,
        arkana_object_id,
        lifetime_seconds: int = DEFAULT_SESSION_LIFETIME_SECONDS,
        session_id: str | None = None,
    ):
        self.user_object = user_object
        self.arkana_object_id = self._resolve_arkana_object_id(arkana_object_id)
        self.arkana_id = self.arkana_object_id
        self.session_id = session_id or self._build_session_id()
        self.lifetime_seconds = max(int(lifetime_seconds), 1)

        self.base_path = _resolve_sessions_root()
        self.session_path = self.base_path / self.session_id
        self.workspace_root_path = self.base_path / "workspaces"
        self.workspace_path = self.workspace_root_path / self.workspace_key
        self.metadata_path = self.session_path / "metadata.json"
        self.docker_bin = self._resolve_docker_bin()

    def run_command(self, sCommand: str) -> ArkanaSessionRunResult:
        self._cleanup_if_expired()
        self._ensure_session_ready()
        self._ensure_runtime_available()
        files_before = self._snapshot_workspace_files()
        command = self._build_exec_command(sCommand)
        started_at = time.monotonic()
        completed = subprocess.run(command, capture_output=True, text=True, check=False)
        runtime_seconds = max(math.ceil(time.monotonic() - started_at), 1)
        self.logg_usage(runtime_seconds)
        files_after = self._snapshot_workspace_files()
        session_files = sorted(files_after - files_before)
        return ArkanaSessionRunResult(
            session_id=self.session_id,
            command=sCommand,
            returncode=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
            runtime_seconds=runtime_seconds,
            session_files=session_files,
        )

    def start_session(self) -> dict[str, Any]:
        self._cleanup_if_expired()
        self.create_volume()
        created = False
        if not self._container_exists():
            self.create_container()
            created = True
        self._write_metadata(
            {
                "session_id": self.session_id,
                "container_name": self.container_name,
                "language": self.language,
                "runtime_type": self.runtime_type,
                "docker_image": self.docker_image,
                "user_id": self.get_user_id(),
                "arkana_object_id": self.arkana_object_id,
                "workspace_path": str(self.workspace_path),
                "created_at": self._now_iso(),
                "expires_at": self._expires_at(self.lifetime_seconds),
                "lifetime_seconds": self.lifetime_seconds,
            }
        )
        return {
            "session_id": self.session_id,
            "container_name": self.container_name,
            "workspace_path": str(self.workspace_path),
            "created": created,
            "state": self.get_session_state(),
        }

    def delete_session(self) -> bool:
        if self._container_exists():
            subprocess.run(self._docker_cmd("rm", "-f", self.container_name), capture_output=True, text=True, check=False)
        if self.session_path.exists():
            shutil.rmtree(self.session_path, ignore_errors=True)
        return True

    def create_volume(self):
        self.workspace_path.mkdir(parents=True, exist_ok=True)
        return str(self.workspace_path)

    def get_volume_path(self) -> str:
        self.create_volume()
        return str(self.workspace_path)

    def create_container(self):
        self.create_volume()
        self._ensure_image_available()
        command = [
            *self._docker_cmd(
                "run",
                "-d",
                "--name",
                self.container_name,
                "--label",
                f"arkana.session_id={self.session_id}",
                "--label",
                f"arkana.user_id={self.get_user_id()}",
                "--label",
                f"arkana.object_id={self.arkana_object_id}",
                "-v",
                f"{self.workspace_path}:{CONTAINER_WORKDIR}",
                "-w",
                CONTAINER_WORKDIR,
                self.docker_image,
            ),
            *self.container_command,
        ]
        completed = subprocess.run(command, capture_output=True, text=True, check=False)
        if completed.returncode != 0:
            raise RuntimeError(completed.stderr.strip() or "Failed to create docker container")
        return completed.stdout.strip()

    def get_file(self, filePath: str):
        path = self.workspace_path / filePath
        if not path.exists() or not path.is_file():
            raise FileNotFoundError(filePath)
        return path.read_text(encoding="utf-8")

    def get_file_path(self, fileName: str) -> str:
        path = self.workspace_path / fileName
        if path.exists() and path.is_file():
            return str(path)
        return ""

    def keep_alive(self, livetime: int):
        self._ensure_session_ready()
        metadata = self._load_metadata()
        remaining = self.get_session_state().get("remaining_seconds", 0)
        new_lifetime = max(int(remaining) + max(int(livetime), 0), 1)
        metadata["expires_at"] = self._expires_at(new_lifetime)
        metadata["lifetime_seconds"] = new_lifetime
        self._write_metadata(metadata)
        return self.get_session_state()

    def get_session_state(self):
        expired = self._is_expired()
        exists = self._container_exists()
        running = self._container_is_running() if exists else False
        expires_at = None
        remaining_seconds = 0

        metadata = self._load_metadata()
        if metadata:
            expires_at = metadata.get("expires_at")
            remaining_seconds = max(self._remaining_seconds(expires_at), 0) if expires_at else 0

        state = "missing"
        if expired:
            state = "expired"
        elif running:
            state = "running"
        elif exists:
            state = "stopped"

        return {
            "session_id": self.session_id,
            "container_name": self.container_name,
            "language": self.language,
            "runtime_type": self.runtime_type,
            "state": state,
            "exists": exists,
            "running": running,
            "expired": expired,
            "expires_at": expires_at,
            "remaining_seconds": remaining_seconds,
            "arkana_object_id": self.arkana_object_id,
            "workspace_path": str(self.workspace_path),
        }

    def get_user_id(self):
        return self.user_object.user_id

    def logg_usage(self, runtime: int):
        accounting = self.user_object.get_accounting_obj().load_by_db()
        accounting.logg_runtime(runtime)
        if hasattr(self.user_object, "main_db"):
            accounting.save(self.user_object.main_db)
        return accounting

    @property
    def container_name(self) -> str:
        return f"arkana-{self.language}-{self.session_id}"

    @property
    def runtime_type(self) -> str:
        return "py" if self.language == "python" else self.language

    @property
    def workspace_key(self) -> str:
        return f"report_{self._slug(self.arkana_object_id)}"

    def _build_session_id(self) -> str:
        arkana_id = self._slug(self.arkana_object_id)
        token = uuid.uuid4().hex[:10]
        return f"{self.language}-{arkana_id}-{token}"

    def _resolve_arkana_object_id(self, arkana_object_id) -> str:
        return str(arkana_object_id)

    def _slug(self, value: Any) -> str:
        text = str(value).strip().lower()
        allowed = [char if char.isalnum() else "-" for char in text]
        slug = "".join(allowed).strip("-")
        return slug or "unknown"

    def _write_metadata(self, payload: dict[str, Any]) -> None:
        self.session_path.mkdir(parents=True, exist_ok=True)
        self.metadata_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def _load_metadata(self) -> dict[str, Any]:
        if not self.metadata_path.exists():
            return {}
        return json.loads(self.metadata_path.read_text(encoding="utf-8"))

    def _snapshot_workspace_files(self) -> set[str]:
        if not self.workspace_path.exists():
            return set()
        return {
            str(path.relative_to(self.workspace_path))
            for path in self.workspace_path.rglob("*")
            if path.is_file()
        }

    def _build_exec_command(self, sCommand: str) -> list[str]:
        return [*self._docker_cmd("exec", self.container_name, "sh", "-lc", sCommand)]

    def _container_exists(self) -> bool:
        completed = subprocess.run(
            self._docker_cmd("container", "inspect", self.container_name),
            capture_output=True,
            text=True,
            check=False,
        )
        return completed.returncode == 0

    def _ensure_runtime_available(self) -> None:
        if getattr(self.user_object, "user_role", "") == "root":
            return
        accounting = self.user_object.get_accounting_obj().load_by_db()
        if accounting.check_for_runtime_available(1):
            return
        raise PermissionError("No runtime available for this user")

    def _ensure_image_available(self) -> None:
        completed = subprocess.run(
            self._docker_cmd("image", "inspect", self.docker_image),
            capture_output=True,
            text=True,
            check=False,
        )
        if completed.returncode == 0:
            return
        raise RuntimeError(
            f"Docker image '{self.docker_image}' is not available locally. "
            f"Pull it first with: docker pull {self.docker_image}"
        )

    def _container_is_running(self) -> bool:
        completed = subprocess.run(
            self._docker_cmd("inspect", "-f", "{{.State.Running}}", self.container_name),
            capture_output=True,
            text=True,
            check=False,
        )
        return completed.returncode == 0 and completed.stdout.strip() == "true"

    def _ensure_session_ready(self) -> None:
        if self._is_expired():
            self.delete_session()
            raise RuntimeError("Session expired")
        if not self._container_exists():
            raise RuntimeError("Session container does not exist")
        if not self._container_is_running():
            completed = subprocess.run(self._docker_cmd("start", self.container_name), capture_output=True, text=True, check=False)
            if completed.returncode != 0:
                raise RuntimeError(completed.stderr.strip() or "Failed to start docker container")

    def _is_expired(self) -> bool:
        metadata = self._load_metadata()
        expires_at = metadata.get("expires_at")
        return bool(expires_at) and self._remaining_seconds(expires_at) <= 0

    def _cleanup_if_expired(self) -> None:
        if self._is_expired():
            self.delete_session()

    def _expires_at(self, lifetime_seconds: int) -> str:
        return (datetime.now(timezone.utc) + timedelta(seconds=lifetime_seconds)).isoformat()

    def _remaining_seconds(self, expires_at: str) -> int:
        return int((datetime.fromisoformat(expires_at) - datetime.now(timezone.utc)).total_seconds())

    def _now_iso(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def _resolve_docker_bin(self) -> str:
        configured = os.getenv("ARKANA_DOCKER_BIN")
        if configured:
            return configured
        detected = shutil.which("docker")
        if detected:
            return detected
        raise RuntimeError(
            "Docker CLI not found in PATH. Install docker in the API container or set ARKANA_DOCKER_BIN."
        )

    def _docker_cmd(self, *args: str) -> list[str]:
        return [self.docker_bin, *args]
