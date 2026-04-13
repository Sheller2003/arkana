from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


def load_env(env_file: str | os.PathLike[str] | None = None) -> None:
    if env_file is not None:
        load_dotenv(dotenv_path=env_file, override=False)
        return

    project_root = Path(__file__).resolve().parents[2]
    load_dotenv(dotenv_path=project_root / ".env", override=False)


@dataclass(frozen=True)
class ArkanaMainDBConfig:
    host: str
    port: int
    database: str
    user: str
    password: str
    keyring_service: str = "arkana/db_credentials"
    api_keyring_service: str = "arkana/api_basic_auth"


@dataclass(frozen=True)
class ApiServerConfig:
    host: str
    port: int


@dataclass(frozen=True)
class AmezitSupabaseConfig:
    url: str
    anon_key: str
    service_role_key: str | None = None
    timeout_seconds: float = 10.0
    ca_bundle: str | None = None
    insecure_ssl: bool = False


def get_main_db_config(env_file: str | os.PathLike[str] | None = None) -> ArkanaMainDBConfig:
    load_env(env_file)

    return ArkanaMainDBConfig(
        host=os.getenv("ARKANA_DB_HOST", "127.0.0.1"),
        port=int(os.getenv("ARKANA_DB_PORT", "3306")),
        database=os.getenv("ARKANA_DB_NAME", "arkana"),
        user=_require_env("ARKANA_DB_USER"),
        password=os.getenv("ARKANA_DB_PASSWORD", ""),
        keyring_service=os.getenv("ARKANA_KEYRING_SERVICE", "arkana/db_credentials"),
        api_keyring_service=os.getenv("ARKANA_API_KEYRING_SERVICE", "arkana/api_basic_auth"),
    )


def get_api_server_config(env_file: str | os.PathLike[str] | None = None) -> ApiServerConfig:
    load_env(env_file)
    return ApiServerConfig(
        host=os.getenv("ARKANA_API_HOST", "127.0.0.1"),
        port=int(os.getenv("ARKANA_API_PORT", "8000")),
    )


def get_amezit_supabase_config(env_file: str | os.PathLike[str] | None = None) -> AmezitSupabaseConfig:
    load_env(env_file)
    return AmezitSupabaseConfig(
        url=_require_env("AMEZIT_SUPABASE_URL"),
        anon_key=_require_env("AMEZIT_SUPABASE_ANON_KEY"),
        service_role_key=os.getenv("AMEZIT_SUPABASE_SERVICE_ROLE_KEY"),
        timeout_seconds=float(os.getenv("AMEZIT_SUPABASE_TIMEOUT_SECONDS", "10")),
        ca_bundle=os.getenv("AMEZIT_SUPABASE_CA_BUNDLE") or None,
        insecure_ssl=os.getenv("AMEZIT_SUPABASE_INSECURE_SSL", "").strip() == "1",
    )


def _require_env(name: str) -> str:
    value = os.getenv(name)
    if value:
        return value
    raise RuntimeError(f"Missing required environment variable: {name}")
