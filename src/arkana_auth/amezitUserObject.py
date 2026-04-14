from __future__ import annotations

from dataclasses import dataclass

from src.arkana_auth.amezit_supabase_service import AmezitSupabaseService, SupabaseClientError
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
        )
        return cls(
            main_db=main_db,
            auth=auth_user,
            supabase_user_id=supabase_user_id,
            supabase_email=supabase_email,
            supabase_access_token=access_token,
        )

    @staticmethod
    def _resolve_arkana_user(*, supabase_user_id: str, email: str) -> AuthUser:
        return AuthUser(
            user_id=supabase_user_id,
            user_name=email,
            user_role="viewer",
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


__all__ = ["AmezitUserObject", "AmezitUserPolicyError"]
