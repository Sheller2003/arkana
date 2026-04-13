#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.arkana_auth.user_manager import UserManager
from src.arkana_mdd_db.config import get_amezit_supabase_config, get_main_db_config
from src.arkana_mdd_db.main_db import ArkanaMainDB

DEFAULT_EMAIL = "niklasf1234@yahoo.com"
DEFAULT_PASSWORD = "20Niklas03"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Test the Supabase login flow and Arkana user sync.")
    parser.add_argument("--env-file", default=str(PROJECT_ROOT / ".env"))
    parser.add_argument("--email", default=DEFAULT_EMAIL)
    parser.add_argument("--password", default=DEFAULT_PASSWORD)
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    try:
        get_amezit_supabase_config(args.env_file)
    except RuntimeError as exc:
        print(f"Supabase-Konfiguration fehlt: {exc}", file=sys.stderr)
        return 2

    main_db = ArkanaMainDB(get_main_db_config(args.env_file))
    user_manager = UserManager(main_db)
    user = user_manager.authenticate(args.email, args.password)
    if user is None:
        print("Login fehlgeschlagen", file=sys.stderr)
        return 1

    reloaded_user = main_db.get_user_by_name(args.email)

    print("login_ok=true")
    print(f"user_class={user.__class__.__name__}")
    print(f"user_id={user.user_id}")
    print(f"user_name={user.user_name}")
    print(f"user_role={user.user_role}")
    print(f"supabase_user_id={getattr(user, 'supabase_user_id', None)}")
    print(f"supabase_email={getattr(user, 'supabase_email', None)}")
    print(f"local_user_synced={reloaded_user is not None}")
    if reloaded_user is not None:
        print(f"local_db_user_id={reloaded_user.user_id}")
        print(f"local_db_user_name={reloaded_user.user_name}")
        print(f"local_db_supabase_user_id={reloaded_user.supabase_user_id}")
        print(f"local_db_supabase_email={reloaded_user.supabase_email}")
        print(f"local_db_groups={main_db._fetchall('SELECT group_id FROM user_group_user WHERE user_id = %s ORDER BY group_id', (reloaded_user.user_id,))}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
