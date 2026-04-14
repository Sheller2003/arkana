from __future__ import annotations

import json
import ssl
from dataclasses import dataclass
from urllib import error, request

from src.arkana_mdd_db.config import AmezitSupabaseConfig


class SupabaseClientError(RuntimeError):
    pass


@dataclass(frozen=True)
class SupabaseClient:
    config: AmezitSupabaseConfig

    def authenticate_user(self, *, email: str, password: str) -> dict[str, object] | None:
        return self._request_json(
            path="/auth/v1/token?grant_type=password",
            payload={"email": email, "password": password},
            api_key=self.config.anon_key,
            bearer_token=self.config.anon_key,
        )

    def get_authenticated_user(self, *, access_token: str) -> dict[str, object] | None:
        return self._request_json(
            path="/auth/v1/user",
            payload=None,
            api_key=self.config.anon_key,
            bearer_token=access_token,
            method="GET",
        )

    def assign_to_group(self, *, user_id: str, group_id: int, access_token: str | None = None) -> None:
        self.call_rpc(
            "assign_to_group",
            {"p_user_id": str(user_id), "p_group_id": int(group_id)},
            access_token=access_token,
        )

    def create_group(
        self,
        *,
        group_name: str,
        is_object: bool | None = None,
        access_token: str | None = None,
    ) -> int:
        payload: dict[str, object] = {"p_group_name": group_name}
        if is_object is not None:
            payload["p_is_object"] = bool(is_object)
        result = self.call_rpc(
            "create_group",
            payload,
            access_token=access_token,
        )
        if result is None:
            raise SupabaseClientError("create_group returned no result")
        return int(result)

    def delete_group(self, *, group_id: int, access_token: str | None = None) -> None:
        self.call_rpc(
            "delete_group",
            {"p_group_id": int(group_id)},
            access_token=access_token,
        )

    def get_group_membership_ids(
        self,
        *,
        supabase_user_id: str,
        candidate_group_ids: list[int],
        access_token: str | None = None,
    ) -> list[int]:
        memberships: list[int] = []
        for group_id in candidate_group_ids:
            result = self.call_rpc(
                "check_user_is_in_group",
                {"p_group_id": int(group_id), "p_user_id": str(supabase_user_id)},
                access_token=access_token,
                use_service_role=True,
            )
            if result is True:
                memberships.append(int(group_id))
        return memberships

    def get_group_members(self, *, group_id: int, access_token: str | None = None) -> list[str]:
        result = self.call_rpc(
            "get_group_members",
            {"p_group_id": int(group_id)},
            access_token=access_token,
            use_service_role=True,
        )
        if not isinstance(result, list):
            return []
        return [str(entry) for entry in result]

    def get_chat(
        self,
        *,
        project_id: int,
        user_id: str | None = None,
        max_entries: int = 20,
        up_to_date: str | None = None,
        access_token: str | None = None,
    ) -> object:
        return self.call_rpc(
            "get_chat",
            {
                "p_project_id": int(project_id),
                "p_user_id": str(user_id) if user_id is not None else None,
                "p_max_entrys": int(max_entries),
                "p_up_to_date": up_to_date,
            },
            access_token=access_token,
        )

    def get_user_credential(self, *, service: str, access_token: str) -> dict[str, str] | None:
        result = self.call_rpc(
            "get_user_cred",
            {"p_service": service},
            access_token=access_token,
        )
        if not isinstance(result, list) or not result:
            return None
        row = result[0]
        if not isinstance(row, dict):
            return None
        return {
            "service": str(row.get("service") or service),
            "ext_user_name": str(row.get("ext_user_name") or ""),
            "pw": str(row.get("pw") or ""),
        }

    def set_user_credential(
        self,
        *,
        service: str,
        password: str,
        ext_user_name: str,
        access_token: str,
    ) -> None:
        self.call_rpc(
            "set_user_cred",
            {
                "p_service": service,
                "p_pwd": password,
                "p_ext_user_name": ext_user_name,
            },
            access_token=access_token,
        )

    def get_group_credential(
        self,
        *,
        service: str,
        group_id: int,
        access_token: str | None = None,
    ) -> dict[str, str] | None:
        result = self.call_rpc(
            "get_group_cred",
            {"p_group_id": int(group_id), "p_service": service},
            access_token=access_token,
            use_service_role=True,
        )
        if not isinstance(result, list) or not result:
            return None
        row = result[0]
        if not isinstance(row, dict):
            return None
        return {
            "service": str(row.get("service") or service),
            "ext_user_name": str(row.get("ext_user_name") or ""),
            "pw": str(row.get("pw") or ""),
        }

    def get_project_overview(
        self,
        *,
        company_id: int,
        user_id: str = "",
        access_token: str | None = None,
    ) -> object:
        return self.call_rpc(
            "get_project_overview",
            {"p_company_id": int(company_id), "p_user_id": user_id},
            access_token=access_token,
        )

    def get_project_parameters_json(
        self,
        *,
        project_id: int,
        env_id: int | None = None,
        access_token: str | None = None,
    ) -> object:
        return self.call_rpc(
            "get_project_parameters_json",
            {"p_project_id": int(project_id), "p_env_id": env_id},
            access_token=access_token,
        )

    def get_project_model(self, *, project_id: int, access_token: str | None = None) -> object:
        return self.call_rpc(
            "getprojectmodel",
            {"p_project_id": int(project_id)},
            access_token=access_token,
        )

    def log_tokens(self, *, used_tokens: int, access_token: str | None = None) -> None:
        self.call_rpc(
            "log_tokens",
            {"p_used_tokens": int(used_tokens)},
            access_token=access_token,
        )

    def start_chat_session(
        self,
        *,
        owner_id: str,
        project_id: int,
        chat_action_type: str,
        access_token: str | None = None,
    ) -> object:
        return self.call_rpc(
            "start_chat_session",
            {
                "p_owner_id": str(owner_id),
                "p_project_id": int(project_id),
                "p_chat_action_type": chat_action_type,
            },
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
        return self.call_rpc(
            "update_parameters",
            {
                "p_project_id": int(project_id),
                "p_group_key": group_key,
                "p_param_name": param_name,
                "p_param_value": param_value,
            },
            access_token=access_token,
        )
        if not isinstance(result, list) or not result:
            return None
        row = result[0]
        if not isinstance(row, dict):
            return None
        return {
            "service": str(row.get("service") or service),
            "ext_user_name": str(row.get("ext_user_name") or ""),
            "pw": str(row.get("pw") or ""),
        }

    def set_group_credential(
        self,
        *,
        service: str,
        group_id: int,
        password: str,
        ext_user_name: str,
        access_token: str | None = None,
    ) -> None:
        self.call_rpc(
            "set_group_cred",
            {
                "p_service": service,
                "p_group_id": int(group_id),
                "p_pwd": password,
                "p_ext_user_name": ext_user_name,
            },
            access_token=access_token,
            use_service_role=True,
        )

    def call_rpc(
        self,
        function_name: str,
        payload: dict[str, object],
        *,
        access_token: str | None = None,
        use_service_role: bool = False,
    ) -> object:
        api_key = self.config.service_role_key if use_service_role and self.config.service_role_key else self.config.anon_key
        bearer_token = self.config.service_role_key if use_service_role and self.config.service_role_key else access_token
        return self._request_json(
            path=f"/rest/v1/rpc/{function_name}",
            payload=payload,
            api_key=api_key,
            bearer_token=bearer_token,
        )

    def _request_json(
        self,
        *,
        path: str,
        payload: dict[str, object] | None,
        api_key: str,
        bearer_token: str | None,
        method: str = "POST",
    ) -> object:
        endpoint = f"{self.config.url.rstrip('/')}{path}"
        headers = {
            "apikey": api_key,
            "Content-Type": "application/json",
        }
        if bearer_token:
            headers["Authorization"] = f"Bearer {bearer_token}"
        data = None if payload is None else json.dumps(payload).encode("utf-8")
        req = request.Request(endpoint, data=data, headers=headers, method=method)
        try:
            with request.urlopen(
                req,
                timeout=self.config.timeout_seconds,
                context=self._build_ssl_context(),
            ) as response:
                body = response.read().decode("utf-8")
        except (error.HTTPError, error.URLError, TimeoutError) as exc:
            raise SupabaseClientError(str(exc)) from exc
        if not body:
            return None
        try:
            return json.loads(body)
        except json.JSONDecodeError as exc:
            raise SupabaseClientError("Supabase returned invalid JSON") from exc

    def _build_ssl_context(self) -> ssl.SSLContext:
        if self.config.insecure_ssl:
            return ssl._create_unverified_context()
        if self.config.ca_bundle:
            return ssl.create_default_context(cafile=self.config.ca_bundle)
        return ssl.create_default_context()


__all__ = ["SupabaseClient", "SupabaseClientError"]
