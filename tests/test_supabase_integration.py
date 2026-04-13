from __future__ import annotations

import os
import ssl
import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.arkana_auth.amezit_supabase_service import AmezitSupabaseService
from src.arkana_auth.supabase_client import SupabaseClientError
from src.arkana_mdd_db.config import get_amezit_supabase_config, load_env


load_env(PROJECT_ROOT / ".env")

if os.getenv("SUPABASE_TEST_INSECURE_SSL") == "1":
    ssl._create_default_https_context = ssl._create_unverified_context


def _require(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise unittest.SkipTest(f"Missing required env var: {name}")
    return value


class SupabaseIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.email = _require("SUPABASE_TEST_EMAIL")
        cls.password = _require("SUPABASE_TEST_PASSWORD")
        cls.user_service_name = os.getenv("SUPABASE_TEST_USER_SERVICE", "test")
        cls.user_ext_user_name = os.getenv("SUPABASE_TEST_USER_EXT_USERNAME", cls.email)
        cls.user_service_password = os.getenv("SUPABASE_TEST_USER_PASSWORD", "passwort")
        cls.group_id = os.getenv("SUPABASE_TEST_GROUP_ID", "").strip()
        cls.group_service_name = os.getenv("SUPABASE_TEST_GROUP_SERVICE", "test-group")
        cls.group_ext_user_name = os.getenv("SUPABASE_TEST_GROUP_EXT_USERNAME", "group-user")
        cls.group_service_password = os.getenv("SUPABASE_TEST_GROUP_PASSWORD", "passwort")
        cls.config = get_amezit_supabase_config(PROJECT_ROOT / ".env")
        cls.service = AmezitSupabaseService.from_config(cls.config)

        auth = cls.service.authenticate_user(email=cls.email, password=cls.password)
        if not isinstance(auth, dict):
            raise unittest.SkipTest("Supabase auth did not return a payload")

        user = auth.get("user") or {}
        cls.access_token = str(auth.get("access_token") or "")
        cls.supabase_user_id = str(user.get("id") or "")
        if not cls.access_token or not cls.supabase_user_id:
            raise unittest.SkipTest("Supabase auth did not return access token or user id")

    def test_authenticate_user(self) -> None:
        auth = self.service.authenticate_user(email=self.email, password=self.password)
        self.assertIsInstance(auth, dict)
        self.assertEqual(str((auth or {}).get("user", {}).get("email") or ""), self.email)

    def test_check_user_group_allowed(self) -> None:
        if not self.group_id:
            self.skipTest("Missing SUPABASE_TEST_GROUP_ID")
        result = self.service.check_user_group_allowed(
            supabase_user_id=self.supabase_user_id,
            group_id=int(self.group_id),
            access_token=self.access_token,
        )
        self.assertIsInstance(result, bool)

    def test_set_and_get_user_credential(self) -> None:
        self.service.set_user_credential(
            service=self.user_service_name,
            password=self.user_service_password,
            ext_user_name=self.user_ext_user_name,
            access_token=self.access_token,
        )
        credential = self.service.get_user_credential(
            service=self.user_service_name,
            access_token=self.access_token,
        )
        self.assertIsNotNone(credential)
        self.assertEqual(str(credential.get("ext_user_name") or ""), self.user_ext_user_name)
        self.assertEqual(str(credential.get("pw") or ""), self.user_service_password)

    def test_set_and_get_group_credential(self) -> None:
        if not self.group_id:
            self.skipTest("Missing SUPABASE_TEST_GROUP_ID")
        self.service.set_group_credential(
            service=self.group_service_name,
            group_id=int(self.group_id),
            password=self.group_service_password,
            ext_user_name=self.group_ext_user_name,
            access_token=self.access_token,
        )
        credential = self.service.get_group_credential(
            service=self.group_service_name,
            group_id=int(self.group_id),
            access_token=self.access_token,
        )
        self.assertIsNotNone(credential)
        self.assertEqual(str(credential.get("ext_user_name") or ""), self.group_ext_user_name)
        self.assertEqual(str(credential.get("pw") or ""), self.group_service_password)

    def test_errors_surface_as_client_errors(self) -> None:
        with self.assertRaises(SupabaseClientError):
            self.service.check_user_group_allowed(
                supabase_user_id=self.supabase_user_id,
                group_id=-1,
                access_token=self.access_token,
            )


if __name__ == "__main__":
    unittest.main()
