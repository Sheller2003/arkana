from __future__ import annotations

import json
import ssl
from dataclasses import dataclass
from typing import Any, Callable
from urllib import error, request

from src.arkana_auth.user_group import UserGroup
from src.arkana_mdd_db.config import AmezitSupabaseConfig


class SupabaseClientError(RuntimeError):
    pass


@dataclass(frozen=True)
class _RpcMethodDefinition:
    method_name: str
    function_name: str
    payload_keys: tuple[tuple[str, str], ...] = ()
    use_service_role: bool = False
    defaults: dict[str, Any] | None = None


DOCUMENTED_RPC_METHODS: tuple[_RpcMethodDefinition, ...] = (
    _RpcMethodDefinition("amezit_cred_decrypt", "amezit_cred_decrypt", (("cipher", "cipher"),)),
    _RpcMethodDefinition("amezit_cred_encrypt", "amezit_cred_encrypt", (("plain", "plain"),)),
    _RpcMethodDefinition(
        "assign_auth_class_to_pplan",
        "assign_auth_class_to_pplan",
        (("pplan_id", "p_pplan_id"), ("auth_key", "p_auth_key")),
    ),
    _RpcMethodDefinition(
        "assign_auth_obj_to_pplan",
        "assign_auth_obj_to_pplan",
        (("pplan_id", "p_pplan_id"), ("auth_key", "p_auth_key")),
    ),
    _RpcMethodDefinition(
        "assign_auth_obj_to_role",
        "assign_auth_obj_to_role",
        (("role_key", "p_role_key"), ("auth_key", "p_auth_key")),
    ),
    _RpcMethodDefinition(
        "assign_auth_obj_to_user",
        "assign_auth_obj_to_user",
        (("user_id", "p_user_id"), ("auth_key", "p_auth_key"), ("auth_value", "p_auth_value")),
    ),
    _RpcMethodDefinition(
        "assign_object_group",
        "assign_object_group",
        (("object_key", "p_object_key"), ("object_id", "p_object_id"), ("group_id", "p_group_id")),
    ),
    _RpcMethodDefinition(
        "assign_pplan_to_user",
        "assign_pplan_to_user",
        (("user_id", "p_user_id"), ("pplan_id", "p_pplan_id")),
    ),
    _RpcMethodDefinition("assign_role", "assign_role", (("role_key", "p_role_key"), ("user_id", "p_user_id"))),
    _RpcMethodDefinition("assign_to_group", "assign_to_group", (("user_id", "p_user_id"), ("group_id", "p_group_id"))),
    _RpcMethodDefinition(
        "assign_to_group_with_role",
        "assign_to_group",
        (("user_id", "p_user_id"), ("group_id", "p_group_id"), ("group_role", "p_group_role")),
    ),
    _RpcMethodDefinition(
        "check_pplan_allows",
        "check_pplan_allows",
        (("auth_key", "p_auth_key"), ("pplan_id", "p_pplan_id"), ("required_value", "p_required_value")),
    ),
    _RpcMethodDefinition(
        "check_user_is_in_group",
        "check_user_is_in_group",
        (("group_id", "p_group_id"), ("user_id", "p_user_id")),
        use_service_role=True,
    ),
    _RpcMethodDefinition(
        "create_auth_obj",
        "create_auth_obj",
        (
            ("auth_key", "p_auth_key"),
            ("auth_value", "p_auth_value"),
            ("auth_class", "p_auth_class"),
            ("is_auth_class", "p_is_auth_class"),
            ("auth_description", "p_auth_description"),
        ),
    ),
    _RpcMethodDefinition(
        "create_group_extended",
        "create_group",
        (
            ("group_name", "p_group_name"),
            ("obj_group", "p_obj_group"),
            ("parent_group", "p_parent_group"),
            ("object_key", "p_object_key"),
        ),
    ),
    _RpcMethodDefinition("create_group", "create_group", (("group_name", "p_group_name"),)),
    _RpcMethodDefinition(
        "create_payment_plan",
        "create_payment_plan",
        (
            ("pplan_name", "p_pplan_name"),
            ("pplan_description", "p_pplan_description"),
            ("pplan_lv", "p_pplan_lv"),
            ("is_active", "p_is_active"),
        ),
    ),
    _RpcMethodDefinition("current_user_payment_plan", "current_user_payment_plan"),
    _RpcMethodDefinition("current_user_role", "current_user_role"),
    _RpcMethodDefinition(
        "delete_auth_class_to_pplan",
        "delete_auth_class_to_pplan",
        (("pplan_id", "p_pplan_id"), ("auth_key", "p_auth_key")),
    ),
    _RpcMethodDefinition(
        "delete_auth_obj_to_role",
        "delete_auth_obj_to_role",
        (("role_key", "p_role_key"), ("auth_key", "p_auth_key")),
    ),
    _RpcMethodDefinition("delete_group", "delete_group", (("group_id", "p_group_id"),)),
    _RpcMethodDefinition("ensure_special_groups", "ensure_special_groups", (("owner", "p_owner"),)),
    _RpcMethodDefinition("get_all_auth_class", "get_all_auth_class"),
    _RpcMethodDefinition("get_all_auth_objs", "get_all_auth_objs"),
    _RpcMethodDefinition("get_all_pplans", "get_all_pplans"),
    _RpcMethodDefinition("get_all_user", "get_all_user"),
    _RpcMethodDefinition("get_all_user_groups", "get_all_user_groups"),
    _RpcMethodDefinition(
        "get_assigned_auth_classes_pplan",
        "get_assigned_auth_classes_pplan",
        (("pplan_id", "p_pplan_id"),),
    ),
    _RpcMethodDefinition("get_assigned_auth_obj_roles", "get_assigned_auth_obj_roles"),
    _RpcMethodDefinition(
        "get_chat",
        "get_chat",
        (
            ("project_id", "p_project_id"),
            ("user_id", "p_user_id"),
            ("max_entries", "p_max_entrys"),
            ("up_to_date", "p_up_to_date"),
        ),
        defaults={"user_id": None, "max_entries": 20, "up_to_date": None},
    ),
    _RpcMethodDefinition(
        "get_effective_user_payment_plan",
        "get_effective_user_payment_plan",
        (("user_id", "p_user_id"),),
    ),
    _RpcMethodDefinition("get_group_cred", "get_group_cred", (("group_id", "p_group_id"), ("service", "p_service"))),
    _RpcMethodDefinition("get_group_info", "get_group_info", (("group_id", "p_group_id"),)),
    _RpcMethodDefinition("get_group_members", "get_group_members", (("group_id", "p_group_id"),)),
    _RpcMethodDefinition("get_groups", "get_groups", (("group_id", "p_group_id"),)),
    _RpcMethodDefinition("get_my_groups", "get_my_groups"),
    _RpcMethodDefinition("get_own_auth", "get_own_auth"),
    _RpcMethodDefinition("get_own_max_limits", "get_own_max_limits"),
    _RpcMethodDefinition("get_own_user_data", "get_own_user_data"),
    _RpcMethodDefinition(
        "get_payment_plan_auth_obj_assignment",
        "get_payment_plan_auth_obj_assignment",
        (("pplan_id", "p_pplan_id"),),
    ),
    _RpcMethodDefinition("get_pplan_limits", "get_pplan_limits", (("pplan_id", "p_pplan_id"),)),
    _RpcMethodDefinition(
        "get_project_overview",
        "get_project_overview",
        (("company_id", "p_company_id"), ("user_id", "p_user_id")),
        defaults={"user_id": ""},
    ),
    _RpcMethodDefinition(
        "get_project_parameters_json",
        "get_project_parameters_json",
        (("project_id", "p_project_id"), ("env_id", "p_env_id")),
        defaults={"env_id": None},
    ),
    _RpcMethodDefinition(
        "get_runtime_usage_period_start",
        "get_runtime_usage_period_start",
        (("period_key", "p_period_key"), ("ref_ts", "p_ref_ts")),
    ),
    _RpcMethodDefinition("get_user_auth", "get_user_auth", (("user_id", "p_user_id"),)),
    _RpcMethodDefinition("get_user_cred", "get_user_cred", (("service", "p_service"),)),
    _RpcMethodDefinition("get_user_roles", "get_user_roles"),
    _RpcMethodDefinition("getprojectmodel", "getprojectmodel", (("project_id", "p_project_id"),)),
    _RpcMethodDefinition(
        "has_auth_class_assignment",
        "has_auth_class_assignment",
        (("user_id", "p_user_id"), ("auth_class", "p_auth_class")),
    ),
    _RpcMethodDefinition(
        "has_effective_auth",
        "has_effective_auth",
        (("user_id", "p_user_id"), ("auth_key", "p_auth_key"), ("required_value", "p_required_value")),
    ),
    _RpcMethodDefinition("is_root_user", "is_root_user", (("user_id", "p_user_id"),)),
    _RpcMethodDefinition("leave_group", "leave_group", (("group_id", "p_group_id"), ("user_id", "p_user_id"))),
    _RpcMethodDefinition(
        "log_runtime_usage",
        "log_runtime_usage",
        (
            ("service_key", "p_service_key"),
            ("runtime_value", "p_runtime_value"),
            ("source_ref", "p_source_ref"),
            ("user_id", "p_user_id"),
        ),
    ),
    _RpcMethodDefinition(
        "log_token_usage",
        "log_token_usage",
        (
            ("model_key", "p_model_key"),
            ("used_tokens", "p_used_tokens"),
            ("source_ref", "p_source_ref"),
            ("user_id", "p_user_id"),
        ),
    ),
    _RpcMethodDefinition("log_tokens", "log_tokens", (("used_tokens", "p_used_tokens"),)),
    _RpcMethodDefinition(
        "remove_company_payed_service",
        "remove_company_payed_service",
        (("company_id", "p_company_id"), ("pservice_id", "p_pservice_id")),
    ),
    _RpcMethodDefinition("remove_from_group", "remove_from_group", (("group_id", "p_group_id"), ("user_id", "p_user_id"))),
    _RpcMethodDefinition(
        "require_effective_auth",
        "require_effective_auth",
        (("auth_key", "p_auth_key"), ("required_value", "p_required_value"), ("user_id", "p_user_id")),
    ),
    _RpcMethodDefinition("require_root_user", "require_root_user", (("user_id", "p_user_id"),)),
    _RpcMethodDefinition(
        "set_company_payed_service",
        "set_company_payed_service",
        (("company_id", "p_company_id"), ("pservice_id", "p_pservice_id")),
    ),
    _RpcMethodDefinition(
        "set_group_cred",
        "set_group_cred",
        (("service", "p_service"), ("group_id", "p_group_id"), ("pwd", "p_pwd"), ("ext_user_name", "p_ext_user_name")),
    ),
    _RpcMethodDefinition(
        "set_runtime_limit_for_pplan",
        "set_runtime_limit_for_pplan",
        (
            ("pplan_id", "p_pplan_id"),
            ("service_key", "p_service_key"),
            ("max_value", "p_max_value"),
            ("is_infinite", "p_infinit"),
            ("period_key", "p_period_key"),
        ),
    ),
    _RpcMethodDefinition(
        "set_token_limit_for_pplan",
        "set_token_limit_for_pplan",
        (
            ("pplan_id", "p_pplan_id"),
            ("model_key", "p_model_key"),
            ("max_tokens", "p_max_tokens"),
            ("is_infinite", "p_infinit"),
            ("period_key", "p_period_key"),
        ),
    ),
    _RpcMethodDefinition("set_updated_at", "set_updated_at"),
    _RpcMethodDefinition(
        "set_user_cred",
        "set_user_cred",
        (("service", "p_service"), ("pwd", "p_pwd"), ("ext_user_name", "p_ext_user_name")),
    ),
    _RpcMethodDefinition(
        "start_chat_session",
        "start_chat_session",
        (("owner_id", "p_owner_id"), ("project_id", "p_project_id"), ("chat_action_type", "p_chat_action_type")),
    ),
    _RpcMethodDefinition(
        "update_parameters",
        "update_parameters",
        (("project_id", "p_project_id"), ("group_key", "p_group_key"), ("param_name", "p_param_name"), ("param_value", "p_param_value")),
    ),
)


DOCUMENTED_RPC_METHOD_NAMES = {definition.method_name: definition.function_name for definition in DOCUMENTED_RPC_METHODS}


@dataclass(frozen=True)
class SupabaseConnector:
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
        self._invoke_documented_rpc(
            "assign_to_group",
            {"user_id": str(user_id), "group_id": int(group_id)},
            access_token=access_token,
        )

    def assign_to_group_with_role(
        self,
        *,
        user_id: str,
        group_id: int,
        group_role: str,
        access_token: str | None = None,
    ) -> None:
        self._invoke_documented_rpc(
            "assign_to_group_with_role",
            {"user_id": str(user_id), "group_id": int(group_id), "group_role": group_role},
            access_token=access_token,
        )

    def create_group(
        self,
        *,
        group_name: str,
        is_object: bool | None = None,
        obj_group: bool | None = None,
        parent_group: int | None = None,
        object_key: str | None = None,
        access_token: str | None = None,
    ) -> int:
        if obj_group is None:
            obj_group = is_object
        if obj_group is not None or parent_group is not None or object_key is not None:
            result = self.create_group_extended(
                group_name=group_name,
                obj_group=bool(obj_group or False),
                parent_group=parent_group,
                object_key=object_key,
                access_token=access_token,
            )
        else:
            result = self._invoke_documented_rpc(
                "create_group",
                {"group_name": group_name},
                access_token=access_token,
            )
        if result is None:
            raise SupabaseClientError("create_group returned no result")
        return int(result)

    def create_group_extended(
        self,
        *,
        group_name: str,
        obj_group: bool = False,
        parent_group: int | None = None,
        object_key: str | None = None,
        access_token: str | None = None,
    ) -> int:
        result = self._invoke_documented_rpc(
            "create_group_extended",
            {
                "group_name": group_name,
                "obj_group": bool(obj_group),
                "parent_group": parent_group,
                "object_key": object_key,
            },
            access_token=access_token,
        )
        if result is None:
            raise SupabaseClientError("create_group_extended returned no result")
        return int(result)

    def delete_group(self, *, group_id: int, access_token: str | None = None) -> None:
        self._invoke_documented_rpc(
            "delete_group",
            {"group_id": int(group_id)},
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
            if self.check_user_is_in_group(group_id=int(group_id), user_id=str(supabase_user_id), access_token=access_token):
                memberships.append(int(group_id))
        return memberships

    def get_group_members(self, *, group_id: int, access_token: str | None = None) -> list[str]:
        result = self._invoke_documented_rpc(
            "get_group_members",
            {"group_id": int(group_id)},
            access_token=access_token,
        )
        if not isinstance(result, list):
            return []
        return [str(entry) for entry in result]

    def check_user_is_in_group(self, *, group_id: int, user_id: str, access_token: str | None = None) -> bool:
        return bool(
            self._invoke_documented_rpc(
                "check_user_is_in_group",
                {"group_id": int(group_id), "user_id": str(user_id)},
                access_token=access_token,
            )
        )

    def get_user_credential(self, *, service: str, access_token: str) -> dict[str, str] | None:
        result = self._invoke_documented_rpc(
            "get_user_cred",
            {"service": service},
            access_token=access_token,
        )
        return self._parse_credential_result(result, service=service)

    def set_user_credential(
        self,
        *,
        service: str,
        password: str,
        ext_user_name: str,
        access_token: str,
    ) -> None:
        self._invoke_documented_rpc(
            "set_user_cred",
            {"service": service, "pwd": password, "ext_user_name": ext_user_name},
            access_token=access_token,
        )

    def get_group_credential(
        self,
        *,
        service: str,
        group_id: int,
        access_token: str | None = None,
    ) -> dict[str, str] | None:
        result = self._invoke_documented_rpc(
            "get_group_cred",
            {"group_id": int(group_id), "service": service},
            access_token=access_token,
        )
        return self._parse_credential_result(result, service=service, group_id=group_id)

    def set_group_credential(
        self,
        *,
        service: str,
        group_id: int,
        password: str,
        ext_user_name: str,
        access_token: str | None = None,
    ) -> None:
        self._invoke_documented_rpc(
            "set_group_cred",
            {"service": service, "group_id": int(group_id), "pwd": password, "ext_user_name": ext_user_name},
            access_token=access_token,
        )

    def get_my_user_groups(self, *, access_token: str) -> list[UserGroup]:
        result = self._invoke_documented_rpc(
            "get_my_groups",
            {},
            access_token=access_token,
        )
        return self._parse_user_groups(result)

    def get_all_user_groups(self, *, access_token: str | None = None) -> list[UserGroup]:
        result = self._invoke_documented_rpc(
            "get_all_user_groups",
            {},
            access_token=access_token,
        )
        return self._parse_user_groups(result)

    def get_groups(self, *, group_id: int, access_token: str | None = None) -> list[UserGroup]:
        result = self._invoke_documented_rpc(
            "get_groups",
            {"group_id": int(group_id)},
            access_token=access_token,
        )
        return self._parse_user_groups(result)

    def get_group_info(self, *, group_id: int, access_token: str | None = None) -> dict[str, Any] | None:
        result = self._invoke_documented_rpc(
            "get_group_info",
            {"group_id": int(group_id)},
            access_token=access_token,
        )
        return result if isinstance(result, dict) else None

    def get_project_model(self, *, project_id: int, access_token: str | None = None) -> object:
        return self._invoke_documented_rpc(
            "getprojectmodel",
            {"project_id": int(project_id)},
            access_token=access_token,
        )

    def log_tokens(self, *, used_tokens: int, access_token: str | None = None) -> None:
        self._invoke_documented_rpc(
            "log_tokens",
            {"used_tokens": int(used_tokens)},
            access_token=access_token,
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

    def _invoke_documented_rpc(
        self,
        method_name: str,
        values: dict[str, Any],
        *,
        access_token: str | None = None,
    ) -> object:
        definition = next((item for item in DOCUMENTED_RPC_METHODS if item.method_name == method_name), None)
        if definition is None:
            raise AttributeError(f"Unknown documented RPC method: {method_name}")
        payload: dict[str, Any] = {}
        defaults = definition.defaults or {}
        for arg_name, payload_key in definition.payload_keys:
            if arg_name in values:
                payload[payload_key] = values[arg_name]
            elif arg_name in defaults:
                payload[payload_key] = defaults[arg_name]
            else:
                raise TypeError(f"Missing required keyword argument: {arg_name}")
        return self.call_rpc(
            definition.function_name,
            payload,
            access_token=access_token,
            use_service_role=definition.use_service_role,
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

    @staticmethod
    def _parse_credential_result(
        result: object,
        *,
        service: str,
        group_id: int | None = None,
    ) -> dict[str, str] | None:
        if not isinstance(result, list) or not result:
            return None
        row = result[0]
        if not isinstance(row, dict):
            return None
        parsed = {
            "service": str(row.get("service") or service),
            "ext_user_name": str(row.get("ext_user_name") or ""),
            "pw": str(row.get("pw") or ""),
        }
        if group_id is not None:
            parsed["group_id"] = str(group_id)
        return parsed

    @staticmethod
    def _parse_user_groups(result: object) -> list[UserGroup]:
        if not isinstance(result, list):
            return []
        return [UserGroup.from_payload(item) for item in result if isinstance(item, dict)]


def _build_documented_rpc_method(definition: _RpcMethodDefinition) -> Callable[..., object]:
    def documented_rpc_method(self: SupabaseConnector, *, access_token: str | None = None, **kwargs: Any) -> object:
        return self._invoke_documented_rpc(definition.method_name, kwargs, access_token=access_token)

    documented_rpc_method.__name__ = definition.method_name
    documented_rpc_method.__qualname__ = f"SupabaseConnector.{definition.method_name}"
    return documented_rpc_method


for _definition in DOCUMENTED_RPC_METHODS:
    if _definition.method_name in SupabaseConnector.__dict__:
        continue
    setattr(SupabaseConnector, _definition.method_name, _build_documented_rpc_method(_definition))


__all__ = ["DOCUMENTED_RPC_METHOD_NAMES", "DOCUMENTED_RPC_METHODS", "SupabaseConnector", "SupabaseClientError"]
