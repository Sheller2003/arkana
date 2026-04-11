from src.arkana_sphere.arkana_session_interface import ArkanaSessionInterface


class ArkanaRSession(ArkanaSessionInterface):
    language = "r"
    docker_image = "r-base:latest"

    def _build_exec_command(self, sCommand: str) -> list[str]:
        return ["docker", "exec", "-i", self.container_name, "Rscript", "-e", sCommand]
