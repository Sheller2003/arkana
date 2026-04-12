from src.arkana_sphere.arkana_session_interface import ArkanaSessionInterface, CONTAINER_WORKDIR


class ArkanaPythonSandboxSession(ArkanaSessionInterface):
    language = "python"
    docker_image = "python:3.11-slim"

    def _build_exec_command(self, sCommand: str) -> list[str]:
        return [*self._docker_cmd("exec", "-i", "-w", CONTAINER_WORKDIR, self.container_name, "python", "-c", sCommand)]
