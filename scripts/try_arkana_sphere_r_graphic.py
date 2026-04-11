from __future__ import annotations

from src.arkana_auth.user_object import ArkanaUser
from src.arkana_mdd_db.config import get_main_db_config
from src.arkana_mdd_db.main_db import ArkanaMainDB
from src.arkana_sphere.arkana_session_manager import ArkanaSessionManager


def load_user(user_name: str) -> ArkanaUser:
    main_db = ArkanaMainDB(get_main_db_config())
    auth_user = main_db.get_user_by_name(user_name)
    if auth_user is None:
        raise ValueError(f"Unknown user: {user_name}")
    return ArkanaUser(main_db=main_db, auth=auth_user)


def main() -> None:
    user = load_user("root_nf")
    session_manager = ArkanaSessionManager()
    session = session_manager.get_session(arkana_object_id=1, user_object=user, runtime_type="r")

    command = (
        'png("hello_r_plot.png", width=800, height=600); '
        "x <- seq(0, 2*pi, length.out=200); "
        "y <- sin(x); "
        'plot(x, y, type="l", lwd=3, col="steelblue", '
        'main="Hello from Arkana R Session", xlab="x", ylab="sin(x)"); '
        "grid(); "
        "dev.off()"
    )
    result = session.run_command(command)

    print(f"session_id={result.get_session_id()}")
    print(f"returncode={result.returncode}")
    print(f"runtime_seconds={result.runtime_seconds}")
    print(f"graphic_path={session.get_file_path('hello_r_plot.png')}")
    if result.get_results():
        print("stdout:")
        print(result.get_results().rstrip())
    if result.get_errors():
        print("stderr:")
        print(result.get_errors().rstrip())
    if result.get_session_files():
        print("session_files:")
        for session_file in result.get_session_files():
            print(session_file)


if __name__ == "__main__":
    main()
