from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from src.arkana_auth.amezit_supabase_service import AmezitSupabaseService, SupabaseClientError
from src.arkana_auth.user_group import UserGroup
from src.arkana_auth.user_object import ArkanaUser
from src.arkana_mdd_db.config import AmezitSupabaseConfig
from src.arkana_mdd_db.main_db import ArkanaMainDB, AuthUser, PersonalUserRecord


class AmezitUserPolicyError(RuntimeError):
    pass


@dataclass(frozen=True)
class AmezitUserObject(ArkanaUser):
    supabase_user_id: str | None = None
    supabase_email: str | None = None
    supabase_access_token: str | None = None
    _auth_payload_loaded: bool = field(init=False, repr=False, compare=False, default=False)
    _auth_payload_cache: object = field(init=False, repr=False, compare=False, default=None)
    _effective_auth_cache: dict[str, int] = field(init=False, repr=False, compare=False, default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "_auth_payload_loaded", False)
        object.__setattr__(self, "_auth_payload_cache", None)
        object.__setattr__(self, "_effective_auth_cache", {})

    @classmethod
    def authenticate(
        cls,
        *,
        main_db: ArkanaMainDB,
        username: str,
        password: str,
        config: AmezitSupabaseConfig,
    ) -> "AmezitUserObject | None":
        service = AmezitSupabaseService.from_config(config)
        supabase_identity = cls._to_supabase_identity(username)
        try:
            response_payload = service.authenticate_user(email=supabase_identity, password=password)
        except SupabaseClientError:
            response_payload = None
        if not isinstance(response_payload, dict):
            return None

        user_payload = response_payload.get("user") or {}
        supabase_user_id = str(user_payload.get("id")) if user_payload.get("id") is not None else None
        supabase_email = str(user_payload.get("email")) if user_payload.get("email") is not None else supabase_identity
        if not supabase_user_id:
            return None
        access_token = response_payload.get("access_token")
        auth_user = cls._resolve_arkana_user(
            supabase_user_id=supabase_user_id,
            email=supabase_email,
            service=service,
            access_token=access_token if isinstance(access_token, str) else None,
        )
        return cls(
            main_db=main_db,
            auth=auth_user,
            supabase_user_id=supabase_user_id,
            supabase_email=supabase_email,
            supabase_access_token=access_token if isinstance(access_token, str) else None,
        )

    @classmethod
    def from_access_token(
        cls,
        *,
        main_db: ArkanaMainDB,
        access_token: str,
        config: AmezitSupabaseConfig,
    ) -> "AmezitUserObject | None":
        service = AmezitSupabaseService.from_config(config)
        try:
            user_payload = service.get_authenticated_user(access_token=access_token)
        except SupabaseClientError:
            user_payload = None
        if not isinstance(user_payload, dict):
            return None

        supabase_user_id = str(user_payload.get("id")) if user_payload.get("id") is not None else None
        supabase_email = str(user_payload.get("email")) if user_payload.get("email") is not None else None
        if not supabase_user_id or not supabase_email:
            return None

        auth_user = cls._resolve_arkana_user(
            supabase_user_id=supabase_user_id,
            email=supabase_email,
            service=service,
            access_token=access_token,
        )
        return cls(
            main_db=main_db,
            auth=auth_user,
            supabase_user_id=supabase_user_id,
            supabase_email=supabase_email,
            supabase_access_token=access_token,
        )

    @staticmethod
    def _resolve_arkana_user(
        *,
        supabase_user_id: str,
        email: str,
        service: AmezitSupabaseService | None = None,
        access_token: str | None = None,
    ) -> AuthUser:
        user_role = "viewer"
        if service is not None and access_token:
            try:
                resolved_role = service.current_user_role(access_token=access_token)
            except SupabaseClientError:
                resolved_role = None
            if resolved_role:
                user_role = str(resolved_role)
        return AuthUser(
            user_id=supabase_user_id,
            user_name=email,
            user_role=user_role,
            user_storage_db_id=None,
            supabase_user_id=supabase_user_id,
            supabase_email=email,
        )

    @staticmethod
    def _to_supabase_identity(username: str) -> str:
        # The external provider uses the raw Supabase login identity,
        # while Arkana reserves the "amezit-" prefix for provider routing.
        if username.startswith("amezit-"):
            return username[len("amezit-") :]
        return username

    def check_user_group_allowed(self, group_id: int) -> bool:
        if group_id == 0:
            return True
        if not self.supabase_user_id or not self.supabase_access_token:
            return False
        service = self._require_service()
        try:
            return service.check_user_group_allowed(
                supabase_user_id=self.supabase_user_id,
                group_id=int(group_id),
                access_token=self.supabase_access_token,
            )
        except SupabaseClientError:
            return False

    def get_user_groups(self) -> list[UserGroup]:
        if not self.supabase_access_token:
            return []
        try:
            return self._require_service().get_my_groups(access_token=self.supabase_access_token)
        except SupabaseClientError:
            return []

    def get_group_members(self, group_id: int) -> list[str]:
        if not self.supabase_access_token:
            return []
        try:
            return self._require_service().get_group_members(group_id=group_id, access_token=self.supabase_access_token)
        except SupabaseClientError:
            return []

    def create_user_group(
        self,
        group_name: str,
        *,
        obj_group: bool | None = None,
        parent_group: int | None = None,
        object_key: str | None = None,
    ) -> int:
        if not self.supabase_access_token:
            raise PermissionError("Supabase access token required")
        try:
            return self._require_service().create_group(
                group_name=group_name,
                is_object=obj_group,
                parent_group=parent_group,
                object_key=object_key,
                access_token=self.supabase_access_token,
            )
        except SupabaseClientError as exc:
            raise PermissionError(str(exc)) from exc

    def assign_user_to_group(self, *, user_id: str, group_id: int, group_role: str | None = None) -> None:
        if not self.supabase_access_token:
            raise PermissionError("Supabase access token required")
        service = self._require_service()
        try:
            if group_role:
                service.client.assign_to_group_with_role(
                    user_id=user_id,
                    group_id=group_id,
                    group_role=group_role,
                    access_token=self.supabase_access_token,
                )
            else:
                service.assign_to_group(
                    user_id=user_id,
                    group_id=group_id,
                    access_token=self.supabase_access_token,
                )
        except SupabaseClientError as exc:
            raise PermissionError(str(exc)) from exc

    def remove_user_from_group(self, *, user_id: str, group_id: int) -> None:
        if not self.supabase_access_token:
            raise PermissionError("Supabase access token required")
        try:
            self._require_service().remove_from_group(
                group_id=group_id,
                user_id=user_id,
                access_token=self.supabase_access_token,
            )
        except SupabaseClientError as exc:
            raise PermissionError(str(exc)) from exc

    def leave_user_group(self, *, group_id: int) -> None:
        if not self.supabase_access_token or not self.supabase_user_id:
            raise PermissionError("Supabase access token required")
        try:
            self._require_service().leave_group(
                group_id=group_id,
                user_id=self.supabase_user_id,
                access_token=self.supabase_access_token,
            )
        except SupabaseClientError as exc:
            raise PermissionError(str(exc)) from exc

    def get_user_auth(self) -> object:
        self._ensure_auth_cache_loaded()
        return self._auth_payload_cache

    def has_effective_auth(self, auth_key: str, required_value: int = 1) -> bool:
        if self.user_role == "root":
            return True
        if not self.supabase_access_token or not self.supabase_user_id:
            return False
        self._ensure_auth_cache_loaded()
        return self._effective_auth_cache.get(str(auth_key), 0) >= int(required_value)

    def has_auth_class_assignment(self, auth_class: str) -> bool:
        if self.user_role == "root":
            return True
        if not self.supabase_access_token or not self.supabase_user_id:
            return False
        self._ensure_auth_cache_loaded()
        return self._effective_auth_cache.get(str(auth_class), 0) > 0

    def can_access_db(self, db_id: int) -> bool:
        db_record = self.main_db.get_db_schema(db_id)
        if db_record is None:
            return False
        return self.check_user_group_allowed(db_record.user_group)

    def get_runtime_db_password(
        self,
        *,
        db_id: int,
        db_user_name: str,
        personal_user: PersonalUserRecord | None,
        group_id: int,
    ) -> str | None:
        if self.supabase_access_token:
            service = self._require_service()
            credential_service = self.build_db_credential_service_name(db_id)
            try:
                if personal_user is not None:
                    credential = service.get_user_credential(service=credential_service, access_token=self.supabase_access_token)
                else:
                    credential = service.get_group_credential(
                        service=credential_service,
                        group_id=group_id,
                        access_token=self.supabase_access_token,
                    )
            except SupabaseClientError:
                credential = None
            if credential and credential.get("ext_user_name") == db_user_name:
                return credential.get("pw")
        return None

    def set_private_db_password(self, db_id: int, db_user_name: str, password: str) -> None:
        personal_user = self.resolve_private_db_user_for_password(db_id, db_user_name)
        if self.supabase_access_token:
            service = self._require_service()
            try:
                service.set_user_credential(
                    service=self.build_db_credential_service_name(db_id),
                    password=password,
                    ext_user_name=db_user_name,
                    access_token=self.supabase_access_token,
                )
                return
            except SupabaseClientError:
                raise PermissionError("Supabase credential update failed")
        else:
            raise PermissionError("Supabase access token required")

    def get_accounting_obj(self):
        return self._build_accounting_obj()

    def invalidate_buffer(self) -> None:
        object.__setattr__(self, "_auth_payload_loaded", False)
        object.__setattr__(self, "_auth_payload_cache", None)
        object.__setattr__(self, "_effective_auth_cache", {})

    def _build_accounting_obj(self):
        from src.arkana_auth.arkana_usage_accounting import ArkanaUsageAccounting

        return ArkanaUsageAccounting(
            self.user_id,
            main_db=self.main_db,
            supabase_service=self._require_service(),
            supabase_access_token=self.supabase_access_token,
        )

    @staticmethod
    def _require_service() -> AmezitSupabaseService:
        return AmezitSupabaseService.from_env()

    def _ensure_auth_cache_loaded(self) -> None:
        if self._auth_payload_loaded:
            return
        payload: object = None
        if self.supabase_access_token and self.supabase_user_id:
            try:
                payload = self._require_service().get_user_auth(
                    user_id=self.supabase_user_id,
                    access_token=self.supabase_access_token,
                )
            except SupabaseClientError:
                payload = None
        object.__setattr__(self, "_auth_payload_cache", payload)
        object.__setattr__(self, "_effective_auth_cache", self._extract_effective_auth_map(payload))
        object.__setattr__(self, "_auth_payload_loaded", True)

    @classmethod
    def _extract_effective_auth_map(cls, payload: object) -> dict[str, int]:
        if payload is None:
            return {}
        if isinstance(payload, dict):
            for nested_key in ("auth", "auths", "effective_auth", "effective_auths", "permissions"):
                nested = payload.get(nested_key)
                if nested is not None:
                    parsed_nested = cls._extract_effective_auth_map(nested)
                    if parsed_nested:
                        return parsed_nested
            parsed_dict = cls._parse_auth_dict(payload)
            if parsed_dict:
                return parsed_dict
        if isinstance(payload, list):
            parsed_list = cls._parse_auth_list(payload)
            if parsed_list:
                return parsed_list
        return {}

    @staticmethod
    def _parse_auth_dict(payload: dict[str, Any]) -> dict[str, int]:
        parsed: dict[str, int] = {}
        for key, value in payload.items():
            if key in {"auth_key", "auth_value"}:
                continue
            normalized = AmezitUserObject._coerce_auth_value(value)
            if normalized is None:
                continue
            parsed[str(key)] = normalized
        if "auth_key" in payload:
            auth_key = payload.get("auth_key")
            normalized = AmezitUserObject._coerce_auth_value(payload.get("auth_value"))
            if auth_key is not None and normalized is not None:
                parsed[str(auth_key)] = normalized
        return parsed

    @staticmethod
    def _parse_auth_list(payload: list[object]) -> dict[str, int]:
        parsed: dict[str, int] = {}
        for entry in payload:
            if isinstance(entry, dict):
                auth_key = entry.get("auth_key")
                normalized = AmezitUserObject._coerce_auth_value(entry.get("auth_value"))
                if auth_key is not None and normalized is not None:
                    parsed[str(auth_key)] = max(parsed.get(str(auth_key), 0), normalized)
                continue
            if isinstance(entry, str):
                parsed[entry] = max(parsed.get(entry, 0), 1)
        return parsed

    @staticmethod
    def _coerce_auth_value(value: object) -> int | None:
        if isinstance(value, bool):
            return 1 if value else 0
        if isinstance(value, int):
            return value
        if isinstance(value, float) and value.is_integer():
            return int(value)
        if isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                return None
            if stripped.lower() in {"true", "yes"}:
                return 1
            if stripped.lower() in {"false", "no"}:
                return 0
            try:
                return int(stripped)
            except ValueError:
                return None
        return None


__all__ = ["AmezitUserObject", "AmezitUserPolicyError"]
