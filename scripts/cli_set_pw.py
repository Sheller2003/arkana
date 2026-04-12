#!/usr/bin/env python3
from __future__ import annotations

import argparse
import getpass
import sys
from pathlib import Path

import keyring
from keyring.errors import KeyringError
from mysql.connector import Error as MySQLError

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.arkana_mdd_db.config import get_main_db_config
from src.arkana_mdd_db.main_db import ArkanaMainDB


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Set the password for an existing personal DB user in the OS keyring."
    )
    parser.add_argument(
        "--env-file",
        default=str(PROJECT_ROOT / ".env"),
        help="Path to the .env file for the arkana main DB connection.",
    )
    return parser.parse_args()


def prompt_non_empty(label: str) -> str:
    while True:
        value = input(f"{label}: ").strip()
        if value:
            return value
        print(f"{label} darf nicht leer sein.", file=sys.stderr)


def prompt_password() -> str:
    while True:
        password = getpass.getpass("Neues Passwort: ")
        password_repeat = getpass.getpass("Neues Passwort wiederholen: ")
        if not password:
            print("Passwort darf nicht leer sein.", file=sys.stderr)
            continue
        if password != password_repeat:
            print("Passwörter stimmen nicht überein.", file=sys.stderr)
            continue
        return password


def build_keyring_username(db_id: int, arkana_user_id: str, db_user_name: str) -> str:
    return f"db:{db_id}|arkana:{arkana_user_id}|dbuser:{db_user_name}"


def main() -> int:
    args = parse_args()

    try:
        config = get_main_db_config(args.env_file)
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    db_identifier = prompt_non_empty("DB (db_id oder db_name)")
    arkana_username = prompt_non_empty("Arkana Username")
    db_username = prompt_non_empty("DB Username")

    main_db = ArkanaMainDB(config)

    try:
        personal_user = main_db.find_personal_user(db_identifier, arkana_username, db_username)
    except MySQLError as exc:
        print(f"Fehler beim Zugriff auf die arkana DB: {exc}", file=sys.stderr)
        return 3

    if personal_user is None:
        print("Kein passender Eintrag in ark_db_personal_user gefunden. Abbruch.", file=sys.stderr)
        return 4

    new_password = prompt_password()
    keyring_username = build_keyring_username(
        personal_user.db_id,
        personal_user.arkana_user_id,
        personal_user.db_user_name,
    )

    try:
        keyring.set_password(config.keyring_service, keyring_username, new_password)
    except KeyringError as exc:
        print(f"Fehler beim Schreiben in den Keyring: {exc}", file=sys.stderr)
        return 5

    print(
        "Passwort gespeichert für "
        f"db_id={personal_user.db_id}, arkana_user={personal_user.arkana_user_name}, "
        f"db_user={personal_user.db_user_name}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
