from __future__ import annotations

from src.arkana_auth.amezitUserObject import AmezitUserObject, AmezitUserPolicyError
from src.arkana_auth.user_object import ArkanaUser
from src.arkana_mdd_db.config import get_amezit_supabase_config
from src.arkana_mdd_db.main_db import ArkanaMainDB


class UserManager:
    def __init__(self, main_db: ArkanaMainDB) -> None:
        self.main_db = main_db

    def authenticate(self, username: str, password: str) -> ArkanaUser | None:
        if username.startswith("amezit-"):
            return self._authenticate_amezit_user(username, password)
        return self._authenticate_arkana_user(username, password)

    def _authenticate_arkana_user(self, username: str, password: str) -> ArkanaUser | None:
        auth_user = self.main_db.authenticate_api_user(username, password)
        if auth_user is None:
            return None
        return ArkanaUser(main_db=self.main_db, auth=auth_user)

    def _authenticate_amezit_user(self, username: str, password: str) -> ArkanaUser | None:
        try:
            config = get_amezit_supabase_config()
        except RuntimeError:
            return None
        return AmezitUserObject.authenticate(
            main_db=self.main_db,
            username=username,
            password=password,
            config=config,
        )


__all__ = ["UserManager", "AmezitUserPolicyError"]
