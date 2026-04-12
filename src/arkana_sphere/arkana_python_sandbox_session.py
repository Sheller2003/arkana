from src.arkana_sphere.arkana_session_interface import ArkanaSessionInterface


class ArkanaPythonSandboxSession(ArkanaSessionInterface):
    language = "python"
    docker_image = "python:3.11-slim"

    def _build_exec_command(self, sCommand: str) -> list[str]:
        return [*self._docker_cmd("exec", "-i", self.container_name, "python", "-c", sCommand)]
