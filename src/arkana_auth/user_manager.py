from __future__ import annotations

import hashlib
import threading
import time
from dataclasses import dataclass

from src.arkana_auth.amezit_supabase_service import AmezitSupabaseService
from src.arkana_auth.amezitUserObject import AmezitUserObject, AmezitUserPolicyError
from src.arkana_auth.user_group import UserGroup
from src.arkana_auth.user_object import ArkanaUser
from src.arkana_mdd_db.config import get_amezit_supabase_config
from src.arkana_mdd_db.main_db import ArkanaMainDB, AuthUser


AUTH_CACHE_TTL_SECONDS = 45 * 60


@dataclass(frozen=True)
class _CachedAuthEntry:
    expires_at: float
    auth: AuthUser
    is_supabase: bool
    supabase_user_id: str | None = None
    supabase_email: str | None = None
    supabase_access_token: str | None = None


class UserManager:
    _auth_cache: dict[str, _CachedAuthEntry] = {}
    _cache_lock = threading.Lock()

    def __init__(self, main_db: ArkanaMainDB) -> None:
        self.main_db = main_db

    def authenticate(self, username: str, password: str) -> ArkanaUser | None:
        cache_key = self._build_cache_key(username, password)
        cached_user = self._load_cached_user(cache_key)
        if cached_user is not None:
            return cached_user

        if self._is_email_login(username):
            user = self._authenticate_supabase_user(username, password)
            if user is None:
                user = self._authenticate_arkana_user(username, password)
        elif username.startswith("amezit-"):
            user = self._authenticate_supabase_user(username, password)
            if user is None:
                user = self._authenticate_arkana_user(username, password)
        else:
            user = self._authenticate_arkana_user(username, password)

        if user is not None:
            self._store_cached_user(cache_key, user)
        return user

    def authenticate_access_token(self, access_token: str) -> ArkanaUser | None:
        normalized = str(access_token).strip()
        if not normalized:
            return None
        cache_key = self._build_access_token_cache_key(normalized)
        cached_user = self._load_cached_user(cache_key)
        if cached_user is not None:
            return cached_user

        try:
            config = get_amezit_supabase_config()
        except RuntimeError:
            return None
        user = AmezitUserObject.from_access_token(
            main_db=self.main_db,
            access_token=normalized,
            config=config,
        )
        if user is not None:
            self._store_cached_user(cache_key, user)
        return user

    @staticmethod
    def _is_email_login(username: str) -> bool:
        normalized = str(username).strip()
        if "@" not in normalized:
            return False
        local_part, _, domain_part = normalized.partition("@")
        return bool(local_part and domain_part and "." in domain_part)

    def _authenticate_arkana_user(self, username: str, password: str) -> ArkanaUser | None:
        auth_user = self.main_db.authenticate_api_user(username, password)
        if auth_user is None:
            return None
        return ArkanaUser(main_db=self.main_db, auth=auth_user)

    def _authenticate_supabase_user(self, username: str, password: str) -> ArkanaUser | None:
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

    @classmethod
    def _build_cache_key(cls, username: str, password: str) -> str:
        digest = hashlib.sha256(f"{username}\0{password}".encode("utf-8")).hexdigest()
        return f"{username}\0{digest}"

    @classmethod
    def _build_access_token_cache_key(cls, access_token: str) -> str:
        digest = hashlib.sha256(access_token.encode("utf-8")).hexdigest()
        return f"bearer\0{digest}"

    def _load_cached_user(self, cache_key: str) -> ArkanaUser | None:
        now = time.monotonic()
        with self._cache_lock:
            entry = self._auth_cache.get(cache_key)
            if entry is None:
                return None
            if entry.expires_at <= now:
                self._auth_cache.pop(cache_key, None)
                return None
        return self._restore_cached_user(entry)

    def _store_cached_user(self, cache_key: str, user: ArkanaUser) -> None:
        entry = _CachedAuthEntry(
            expires_at=time.monotonic() + AUTH_CACHE_TTL_SECONDS,
            auth=user.auth,
            is_supabase=isinstance(user, AmezitUserObject),
            supabase_user_id=getattr(user, "supabase_user_id", None),
            supabase_email=getattr(user, "supabase_email", None),
            supabase_access_token=getattr(user, "supabase_access_token", None),
        )
        with self._cache_lock:
            self._auth_cache[cache_key] = entry

    def _restore_cached_user(self, entry: _CachedAuthEntry) -> ArkanaUser:
        if entry.is_supabase:
            return AmezitUserObject(
                main_db=self.main_db,
                auth=entry.auth,
                supabase_user_id=entry.supabase_user_id,
                supabase_email=entry.supabase_email,
                supabase_access_token=entry.supabase_access_token,
            )
        return ArkanaUser(main_db=self.main_db, auth=entry.auth)

    @staticmethod
    def _build_supabase_service() -> AmezitSupabaseService:
        return AmezitSupabaseService.from_env()

    def get_user_groups(self, user: ArkanaUser) -> list[UserGroup]:
        if isinstance(user, AmezitUserObject):
            return user.get_user_groups()
        return []

    def create_group(
        self,
        user: ArkanaUser,
        *,
        group_name: str,
        obj_group: bool | None = None,
        parent_group: int | None = None,
        object_key: str | None = None,
    ) -> int:
        return user.create_user_group(
            group_name,
            obj_group=obj_group,
            parent_group=parent_group,
            object_key=object_key,
        )

    def assign_user_to_group(
        self,
        user: ArkanaUser,
        *,
        target_user_id: str,
        group_id: int,
        group_role: str | None = None,
    ) -> None:
        user.assign_user_to_group(user_id=target_user_id, group_id=group_id, group_role=group_role)

    def remove_user_from_group(self, user: ArkanaUser, *, target_user_id: str, group_id: int) -> None:
        user.remove_user_from_group(user_id=target_user_id, group_id=group_id)

    def get_group_members(self, user: ArkanaUser, *, group_id: int) -> list[str]:
        return user.get_group_members(group_id)

    def reload_user_buffer(self, user_id: str) -> int:
        normalized_user_id = str(user_id)
        removed = 0
        with self._cache_lock:
            cache_keys = [
                cache_key
                for cache_key, entry in self._auth_cache.items()
                if entry.auth.user_id == normalized_user_id or str(entry.supabase_user_id or "") == normalized_user_id
            ]
            for cache_key in cache_keys:
                self._auth_cache.pop(cache_key, None)
            removed = len(cache_keys)
        return removed


__all__ = ["UserManager", "AmezitUserPolicyError"]
