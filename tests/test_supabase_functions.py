from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.arkana_auth.amezit_supabase_service import AmezitSupabaseService
from src.arkana_auth.arkana_usage_accounting import ArkanaUsageAccounting
from src.arkana_auth.supabase_client import SupabaseClient
from src.arkana_mdd_db.config import AmezitSupabaseConfig


class SupabaseClientTests(unittest.TestCase):
    def setUp(self) -> None:
        self.config = AmezitSupabaseConfig(
            url="https://example.supabase.co",
            anon_key="anon-key",
            service_role_key="service-role-key",
            timeout_seconds=5.0,
            ca_bundle=None,
            insecure_ssl=False,
        )
        self.client = SupabaseClient(self.config)

    def test_authenticate_user_calls_token_endpoint(self) -> None:
        with patch.object(SupabaseClient, "_request_json", return_value={"access_token": "token"}) as request_json:
            result = self.client.authenticate_user(email="user@example.com", password="secret")

        self.assertEqual(result, {"access_token": "token"})
        request_json.assert_called_once_with(
            path="/auth/v1/token?grant_type=password",
            payload={"email": "user@example.com", "password": "secret"},
            api_key="anon-key",
            bearer_token="anon-key",
        )

    def test_get_group_membership_ids_collects_positive_matches(self) -> None:
        with patch.object(SupabaseClient, "call_rpc", side_effect=[True, False, True]) as call_rpc:
            result = self.client.get_group_membership_ids(
                supabase_user_id="user-123",
                candidate_group_ids=[10, 11, 12],
                access_token="token",
            )

        self.assertEqual(result, [10, 12])
        self.assertEqual(call_rpc.call_count, 3)

    def test_get_user_credential_returns_first_row(self) -> None:
        with patch.object(
            SupabaseClient,
            "call_rpc",
            return_value=[{"service": "svc", "ext_user_name": "db_user", "pw": "pw123"}],
        ):
            result = self.client.get_user_credential(service="svc", access_token="token")

        self.assertEqual(
            result,
            {"service": "svc", "ext_user_name": "db_user", "pw": "pw123"},
        )

    def test_get_user_credential_returns_none_for_empty_result(self) -> None:
        with patch.object(SupabaseClient, "call_rpc", return_value=[]):
            result = self.client.get_user_credential(service="svc", access_token="token")

        self.assertIsNone(result)

    def test_set_user_credential_calls_rpc(self) -> None:
        with patch.object(SupabaseClient, "call_rpc", return_value=None) as call_rpc:
            self.client.set_user_credential(
                service="svc",
                password="pw123",
                ext_user_name="db_user",
                access_token="token",
            )

        call_rpc.assert_called_once_with(
            "set_user_cred",
            {"p_service": "svc", "p_pwd": "pw123", "p_ext_user_name": "db_user"},
            access_token="token",
        )

    def test_get_group_credential_returns_first_row(self) -> None:
        with patch.object(
            SupabaseClient,
            "get_group_credential",
            return_value={"service": "svc", "ext_user_name": "group_user", "pw": "pw123"},
        ):
            result = self.client.get_group_credential(service="svc", group_id=42, access_token="token")

        self.assertEqual(
            result,
            {"service": "svc", "ext_user_name": "group_user", "pw": "pw123"},
        )

    def test_set_group_credential_calls_rpc_with_service_role(self) -> None:
        with patch.object(SupabaseClient, "call_rpc", return_value=None) as call_rpc:
            self.client.set_group_credential(
                service="svc",
                group_id=42,
                password="pw123",
                ext_user_name="group_user",
                access_token="token",
            )

        call_rpc.assert_called_once_with(
            "set_group_cred",
            {"p_service": "svc", "p_group_id": 42, "p_pwd": "pw123", "p_ext_user_name": "group_user"},
            access_token="token",
            use_service_role=True,
        )

    def test_create_group_calls_rpc_and_returns_group_id(self) -> None:
        with patch.object(SupabaseClient, "call_rpc", return_value=123) as call_rpc:
            result = self.client.create_group(group_name="new-group", is_object=True, access_token="token")

        self.assertEqual(result, 123)
        call_rpc.assert_called_once_with(
            "create_group",
            {"p_group_name": "new-group", "p_is_object": True},
            access_token="token",
        )

    def test_delete_group_calls_rpc(self) -> None:
        with patch.object(SupabaseClient, "call_rpc", return_value=None) as call_rpc:
            self.client.delete_group(group_id=123, access_token="token")

        call_rpc.assert_called_once_with(
            "delete_group",
            {"p_group_id": 123},
            access_token="token",
        )

    def test_call_rpc_uses_service_role_if_requested(self) -> None:
        with patch.object(SupabaseClient, "_request_json", return_value={"ok": True}) as request_json:
            result = self.client.call_rpc(
                "check_user_is_in_group",
                {"p_group_id": 10, "p_user_id": "user-123"},
                access_token="user-token",
                use_service_role=True,
            )

        self.assertEqual(result, {"ok": True})
        request_json.assert_called_once_with(
            path="/rest/v1/rpc/check_user_is_in_group",
            payload={"p_group_id": 10, "p_user_id": "user-123"},
            api_key="service-role-key",
            bearer_token="service-role-key",
        )

    def test_call_rpc_falls_back_to_anon_key_without_service_role_key(self) -> None:
        client = SupabaseClient(
            AmezitSupabaseConfig(
                url="https://example.supabase.co",
                anon_key="anon-key",
                service_role_key=None,
                timeout_seconds=5.0,
                ca_bundle=None,
                insecure_ssl=False,
            )
        )
        with patch.object(SupabaseClient, "_request_json", return_value={"ok": True}) as request_json:
            client.call_rpc(
                "check_user_is_in_group",
                {"p_group_id": 10, "p_user_id": "user-123"},
                access_token="user-token",
                use_service_role=True,
            )

        request_json.assert_called_once_with(
            path="/rest/v1/rpc/check_user_is_in_group",
            payload={"p_group_id": 10, "p_user_id": "user-123"},
            api_key="anon-key",
            bearer_token="user-token",
        )

    def test_log_tokens_calls_rpc(self) -> None:
        with patch.object(SupabaseClient, "call_rpc", return_value=None) as call_rpc:
            self.client.log_tokens(used_tokens=123, access_token="token")

        call_rpc.assert_called_once_with(
            "log_tokens",
            {"p_used_tokens": 123},
            access_token="token",
        )

    def test_get_group_credential_returns_first_row_from_rpc(self) -> None:
        with patch.object(
            SupabaseClient,
            "call_rpc",
            return_value=[{"service": "svc", "ext_user_name": "group_user", "pw": "pw123"}],
        ) as call_rpc:
            result = self.client.get_group_credential(service="svc", group_id=42, access_token="token")

        self.assertEqual(
            result,
            {"service": "svc", "ext_user_name": "group_user", "pw": "pw123"},
        )
        call_rpc.assert_called_once_with(
            "get_group_cred",
            {"p_group_id": 42, "p_service": "svc"},
            access_token="token",
            use_service_role=True,
        )

    def test_build_ssl_context_uses_unverified_context_when_configured(self) -> None:
        client = SupabaseClient(
            AmezitSupabaseConfig(
                url="https://example.supabase.co",
                anon_key="anon-key",
                service_role_key=None,
                timeout_seconds=5.0,
                ca_bundle=None,
                insecure_ssl=True,
            )
        )

        with patch("src.arkana_auth.supabase_client.ssl._create_unverified_context", return_value="CTX") as create_ctx:
            result = client._build_ssl_context()

        self.assertEqual(result, "CTX")
        create_ctx.assert_called_once_with()


class AmezitSupabaseServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = MagicMock()
        self.service = AmezitSupabaseService(client=self.client)

    def test_authenticate_user_delegates_to_client(self) -> None:
        self.client.authenticate_user.return_value = {"access_token": "token"}

        result = self.service.authenticate_user(email="user@example.com", password="secret")

        self.assertEqual(result, {"access_token": "token"})
        self.client.authenticate_user.assert_called_once_with(email="user@example.com", password="secret")

    def test_check_user_group_allowed_delegates_to_rpc(self) -> None:
        self.client.call_rpc.return_value = True

        result = self.service.check_user_group_allowed(
            supabase_user_id="user-123",
            group_id=77,
            access_token="token",
        )

        self.assertTrue(result)
        self.client.call_rpc.assert_called_once_with(
            "check_user_is_in_group",
            {"p_group_id": 77, "p_user_id": "user-123"},
            access_token="token",
        )

    def test_create_group_delegates_to_client(self) -> None:
        self.client.create_group.return_value = 123

        result = self.service.create_group(group_name="new-group", is_object=True, access_token="token")

        self.assertEqual(result, 123)
        self.client.create_group.assert_called_once_with(
            group_name="new-group",
            is_object=True,
            access_token="token",
        )

    def test_delete_group_delegates_to_client(self) -> None:
        self.service.delete_group(group_id=123, access_token="token")

        self.client.delete_group.assert_called_once_with(group_id=123, access_token="token")

    def test_get_user_credential_delegates_to_client(self) -> None:
        self.client.get_user_credential.return_value = {"service": "svc", "ext_user_name": "u", "pw": "p"}

        result = self.service.get_user_credential(service="svc", access_token="token")

        self.assertEqual(result, {"service": "svc", "ext_user_name": "u", "pw": "p"})
        self.client.get_user_credential.assert_called_once_with(service="svc", access_token="token")

    def test_set_user_credential_delegates_to_client(self) -> None:
        self.service.set_user_credential(
            service="svc",
            password="pw123",
            ext_user_name="db_user",
            access_token="token",
        )

        self.client.set_user_credential.assert_called_once_with(
            service="svc",
            password="pw123",
            ext_user_name="db_user",
            access_token="token",
        )

    def test_get_group_credential_delegates_to_client(self) -> None:
        self.client.get_group_credential.return_value = {"service": "svc", "ext_user_name": "u", "pw": "p"}

        result = self.service.get_group_credential(service="svc", group_id=10, access_token="token")

        self.assertEqual(result, {"service": "svc", "ext_user_name": "u", "pw": "p"})
        self.client.get_group_credential.assert_called_once_with(
            service="svc",
            group_id=10,
            access_token="token",
        )

    def test_set_group_credential_delegates_to_client(self) -> None:
        self.service.set_group_credential(
            service="svc",
            group_id=10,
            password="pw123",
            ext_user_name="group_user",
            access_token="token",
        )

        self.client.set_group_credential.assert_called_once_with(
            service="svc",
            group_id=10,
            password="pw123",
            ext_user_name="group_user",
            access_token="token",
        )

    def test_log_tokens_delegates_to_client(self) -> None:
        self.service.log_tokens(used_tokens=42, access_token="token")

        self.client.log_tokens.assert_called_once_with(used_tokens=42, access_token="token")


class SupabaseUsageAccountingTests(unittest.TestCase):
    def test_logg_token_uses_supabase_service(self) -> None:
        supabase_service = MagicMock()
        accounting = ArkanaUsageAccounting(
            "user-123",
            supabase_service=supabase_service,
            supabase_access_token="token",
        )

        result = accounting.logg_token(25)

        self.assertEqual(result, 25)
        supabase_service.log_tokens.assert_called_once_with(used_tokens=25, access_token="token")

    def test_save_is_noop_for_supabase_accounting(self) -> None:
        supabase_service = MagicMock()
        accounting = ArkanaUsageAccounting(
            "user-123",
            supabase_service=supabase_service,
            supabase_access_token="token",
        )

        accounting.save(MagicMock())

        supabase_service.log_tokens.assert_not_called()


if __name__ == "__main__":
    unittest.main()
