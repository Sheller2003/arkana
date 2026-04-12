from src.arkana_sphere.arkana_session_interface import ArkanaSessionInterface, CONTAINER_WORKDIR


class ArkanaRSession(ArkanaSessionInterface):
    language = "r"
    docker_image = "r-base:latest"

    def _build_exec_command(self, sCommand: str) -> list[str]:
        return [*self._docker_cmd("exec", "-i", "-w", CONTAINER_WORKDIR, self.container_name, "Rscript", "-e", sCommand)]
