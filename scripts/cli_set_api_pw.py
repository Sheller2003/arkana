#!/usr/bin/env python3
from __future__ import annotations

import argparse
import getpass
import sys
from pathlib import Path

import keyring
from keyring.errors import KeyringError

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.arkana_mdd_db.config import get_main_db_config


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Set a basic-auth password in the OS keyring.")
    parser.add_argument("--env-file", default=str(PROJECT_ROOT / ".env"))
    parser.add_argument("--username", help="API username; if omitted it will be prompted.")
    return parser.parse_args()


def prompt_password() -> str:
    while True:
        password = getpass.getpass("API Passwort: ")
        repeated = getpass.getpass("API Passwort wiederholen: ")
        if not password:
            print("Passwort darf nicht leer sein.", file=sys.stderr)
            continue
        if password != repeated:
            print("Passwörter stimmen nicht überein.", file=sys.stderr)
            continue
        return password


def main() -> int:
    args = parse_args()
    config = get_main_db_config(args.env_file)
    username = args.username or input("API Username: ").strip()
    if not username:
        print("API Username darf nicht leer sein.", file=sys.stderr)
        return 2
    password = prompt_password()
    try:
        keyring.set_password(config.api_keyring_service, username, password)
    except KeyringError as exc:
        print(f"Fehler beim Schreiben in den Keyring: {exc}", file=sys.stderr)
        return 3
    print(f"API Passwort gespeichert fuer {username}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
