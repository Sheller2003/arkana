from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ArkanaSessionRunResult:
    session_id: str
    command: str
    returncode: int
    stdout: str = ""
    stderr: str = ""
    runtime_seconds: int = 0
    session_files: list[str] = field(default_factory=list)

    def get_session_id(self) -> str:
        return self.session_id

    def get_errors(self) -> str:
        return self.stderr

    def get_results(self) -> str:
        return self.stdout

    def get_session_files(self) -> list[str]:
        # returns all during the run command new created files
        return list(self.session_files)

    def loggs(self) -> str:
        if self.stderr:
            return self.stderr
        return self.stdout

    def is_success(self) -> bool:
        return self.returncode == 0

    def to_dict(self) -> dict[str, object]:
        return {
            "session_id": self.session_id,
            "command": self.command,
            "returncode": self.returncode,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "runtime_seconds": self.runtime_seconds,
            "session_files": list(self.session_files),
        }
