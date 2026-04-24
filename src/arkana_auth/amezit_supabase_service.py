from __future__ import annotations

from dataclasses import dataclass

from src.arkana_auth.supabase_client import SupabaseClient, SupabaseClientError
from src.arkana_auth.user_group import UserGroup
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

    def get_authenticated_user(self, *, access_token: str) -> dict[str, object] | None:
        return self.client.get_authenticated_user(access_token=access_token)

    def assign_to_group(self, *, user_id: str, group_id: int, access_token: str | None) -> None:
        self.client.assign_to_group(user_id=user_id, group_id=group_id, access_token=access_token)

    def create_group(
        self,
        *,
        group_name: str,
        is_object: bool | None = None,
        parent_group: int | None = None,
        object_key: str | None = None,
        access_token: str | None,
    ) -> int:
        return self.client.create_group(
            group_name=group_name,
            is_object=is_object,
            parent_group=parent_group,
            object_key=object_key,
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
        return self.client.check_user_is_in_group(
            group_id=group_id,
            user_id=supabase_user_id,
            access_token=access_token,
        )

    def get_group_members(self, *, group_id: int, access_token: str | None) -> list[str]:
        return self.client.get_group_members(group_id=group_id, access_token=access_token)

    def get_my_groups(self, *, access_token: str) -> list[UserGroup]:
        return self.client.get_my_user_groups(access_token=access_token)

    def get_groups(self, *, group_id: int, access_token: str | None) -> list[UserGroup]:
        return self.client.get_groups(group_id=group_id, access_token=access_token)

    def get_all_user_groups(self, *, access_token: str | None = None) -> list[UserGroup]:
        return self.client.get_all_user_groups(access_token=access_token)

    def get_group_info(self, *, group_id: int, access_token: str | None = None) -> dict[str, object] | None:
        return self.client.get_group_info(group_id=group_id, access_token=access_token)

    def remove_from_group(self, *, group_id: int, user_id: str, access_token: str | None) -> None:
        self.client.remove_from_group(group_id=group_id, user_id=user_id, access_token=access_token)

    def leave_group(self, *, group_id: int, user_id: str, access_token: str | None) -> None:
        self.client.leave_group(group_id=group_id, user_id=user_id, access_token=access_token)

    def get_user_auth(self, *, user_id: str, access_token: str | None = None) -> object:
        return self.client.get_user_auth(user_id=user_id, access_token=access_token)

    def has_effective_auth(
        self,
        *,
        user_id: str,
        auth_key: str,
        required_value: int,
        access_token: str | None = None,
    ) -> bool:
        return bool(
            self.client.has_effective_auth(
                user_id=user_id,
                auth_key=auth_key,
                required_value=required_value,
                access_token=access_token,
            )
        )

    def has_auth_class_assignment(
        self,
        *,
        user_id: str,
        auth_class: str,
        access_token: str | None = None,
    ) -> bool:
        return bool(
            self.client.has_auth_class_assignment(
                user_id=user_id,
                auth_class=auth_class,
                access_token=access_token,
            )
        )

    def current_user_role(self, *, access_token: str | None = None) -> str | None:
        result = self.client.current_user_role(access_token=access_token)
        return None if result is None else str(result)

    def current_user_payment_plan(self, *, access_token: str | None = None) -> int | None:
        result = self.client.current_user_payment_plan(access_token=access_token)
        return None if result is None else int(result)

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
