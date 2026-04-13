from __future__ import annotations

from dataclasses import dataclass

from src.arkana_auth.supabase_client import SupabaseClient, SupabaseClientError
from src.arkana_mdd_db.config import AmezitSupabaseConfig, get_amezit_supabase_config


@dataclass(frozen=True)
class AmezitSupabaseService:
    client: SupabaseClient

    @classmethod
    def from_config(cls, config: AmezitSupabaseConfig) -> "AmezitSupabaseService":
        return cls(client=SupabaseClient(config))

    @classmethod
    def from_env(cls) -> "AmezitSupabaseService":
        return cls.from_config(get_amezit_supabase_config())

    def authenticate_user(self, *, email: str, password: str) -> dict[str, object] | None:
        return self.client.authenticate_user(email=email, password=password)

    def assign_to_group(self, *, user_id: str, group_id: int, access_token: str | None) -> None:
        self.client.assign_to_group(user_id=user_id, group_id=group_id, access_token=access_token)

    def create_group(
        self,
        *,
        group_name: str,
        is_object: bool | None = None,
        access_token: str | None,
    ) -> int:
        return self.client.create_group(
            group_name=group_name,
            is_object=is_object,
            access_token=access_token,
        )

    def delete_group(self, *, group_id: int, access_token: str | None) -> None:
        self.client.delete_group(group_id=group_id, access_token=access_token)

    def check_user_group_allowed(
        self,
        *,
        supabase_user_id: str,
        group_id: int,
        access_token: str | None,
    ) -> bool:
        result = self.client.call_rpc(
            "check_user_is_in_group",
            {"p_group_id": int(group_id), "p_user_id": str(supabase_user_id)},
            access_token=access_token,
        )
        return bool(result)

    def get_group_members(self, *, group_id: int, access_token: str | None) -> list[str]:
        return self.client.get_group_members(group_id=group_id, access_token=access_token)

    def get_chat(
        self,
        *,
        project_id: int,
        user_id: str | None = None,
        max_entries: int = 20,
        up_to_date: str | None = None,
        access_token: str | None = None,
    ) -> object:
        return self.client.get_chat(
            project_id=project_id,
            user_id=user_id,
            max_entries=max_entries,
            up_to_date=up_to_date,
            access_token=access_token,
        )

    def get_user_credential(self, *, service: str, access_token: str) -> dict[str, str] | None:
        return self.client.get_user_credential(service=service, access_token=access_token)

    def set_user_credential(
        self,
        *,
        service: str,
        password: str,
        ext_user_name: str,
        access_token: str,
    ) -> None:
        self.client.set_user_credential(
            service=service,
            password=password,
            ext_user_name=ext_user_name,
            access_token=access_token,
        )

    def get_group_credential(
        self,
        *,
        service: str,
        group_id: int,
        access_token: str | None,
    ) -> dict[str, str] | None:
        return self.client.get_group_credential(
            service=service,
            group_id=group_id,
            access_token=access_token,
        )

    def set_group_credential(
        self,
        *,
        service: str,
        group_id: int,
        password: str,
        ext_user_name: str,
        access_token: str | None,
    ) -> None:
        self.client.set_group_credential(
            service=service,
            group_id=group_id,
            password=password,
            ext_user_name=ext_user_name,
            access_token=access_token,
        )

    def get_project_overview(
        self,
        *,
        company_id: int,
        user_id: str = "",
        access_token: str | None = None,
    ) -> object:
        return self.client.get_project_overview(
            company_id=company_id,
            user_id=user_id,
            access_token=access_token,
        )

    def get_project_parameters_json(
        self,
        *,
        project_id: int,
        env_id: int | None = None,
        access_token: str | None = None,
    ) -> object:
        return self.client.get_project_parameters_json(
            project_id=project_id,
            env_id=env_id,
            access_token=access_token,
        )

    def get_project_model(self, *, project_id: int, access_token: str | None = None) -> object:
        return self.client.get_project_model(project_id=project_id, access_token=access_token)

    def log_tokens(self, *, used_tokens: int, access_token: str | None = None) -> None:
        self.client.log_tokens(used_tokens=used_tokens, access_token=access_token)

    def start_chat_session(
        self,
        *,
        owner_id: str,
        project_id: int,
        chat_action_type: str,
        access_token: str | None = None,
    ) -> object:
        return self.client.start_chat_session(
            owner_id=owner_id,
            project_id=project_id,
            chat_action_type=chat_action_type,
            access_token=access_token,
        )

    def update_parameters(
        self,
        *,
        project_id: int,
        group_key: str,
        param_name: str,
        param_value: str | None,
        access_token: str | None = None,
    ) -> object:
        return self.client.update_parameters(
            project_id=project_id,
            group_key=group_key,
            param_name=param_name,
            param_value=param_value,
            access_token=access_token,
        )


__all__ = ["AmezitSupabaseService", "SupabaseClientError"]
