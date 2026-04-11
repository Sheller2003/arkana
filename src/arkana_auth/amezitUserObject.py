from __future__ import annotations

import json
from dataclasses import dataclass
from urllib import error, request

from src.arkana_auth.user_object import ArkanaUser
from src.arkana_mdd_db.config import AmezitSupabaseConfig
from src.arkana_mdd_db.main_db import ArkanaMainDB, AuthUser


class AmezitUserPolicyError(RuntimeError):
    pass


@dataclass(frozen=True)
class AmezitUserObject(ArkanaUser):
    supabase_user_id: str | None = None
    supabase_email: str | None = None

    @classmethod
    def authenticate(
        cls,
        *,
        main_db: ArkanaMainDB,
        username: str,
        password: str,
        config: AmezitSupabaseConfig,
    ) -> "AmezitUserObject | None":
        supabase_identity = cls._to_supabase_identity(username)
        response_payload = cls._authenticate_against_supabase(
            identity=supabase_identity,
            password=password,
            config=config,
        )
        if response_payload is None:
            return None

        auth_user = cls._resolve_arkana_user(main_db=main_db, username=username)

        user_payload = response_payload.get("user") or {}
        return cls(
            main_db=main_db,
            auth=auth_user,
            supabase_user_id=str(user_payload.get("id")) if user_payload.get("id") is not None else None,
            supabase_email=str(user_payload.get("email")) if user_payload.get("email") is not None else supabase_identity,
        )

    @staticmethod
    def _resolve_arkana_user(*, main_db: ArkanaMainDB, username: str) -> AuthUser:
        auth_user = main_db.get_user_by_name(username)
        if auth_user is None:
            return AuthUser(
                user_id=username,
                user_name=username,
                user_role="viewer",
                user_storage_db_id=None,
            )
        if auth_user.user_role == "root":
            raise AmezitUserPolicyError("Amezit users may not have the root role")
        return auth_user

    @staticmethod
    def _to_supabase_identity(username: str) -> str:
        # The external provider uses the raw Supabase login identity,
        # while Arkana reserves the "amezit-" prefix for provider routing.
        if username.startswith("amezit-"):
            return username[len("amezit-") :]
        return username

    @staticmethod
    def _authenticate_against_supabase(
        *,
        identity: str,
        password: str,
        config: AmezitSupabaseConfig,
    ) -> dict[str, object] | None:
        endpoint = f"{config.url.rstrip('/')}/auth/v1/token?grant_type=password"
        payload = json.dumps({"email": identity, "password": password}).encode("utf-8")
        req = request.Request(
            endpoint,
            data=payload,
            headers={
                "apikey": config.anon_key,
                "Authorization": f"Bearer {config.anon_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with request.urlopen(req, timeout=config.timeout_seconds) as response:
                return json.loads(response.read().decode("utf-8"))
        except (error.HTTPError, error.URLError, TimeoutError, json.JSONDecodeError):
            return None


__all__ = ["AmezitUserObject", "AmezitUserPolicyError"]
