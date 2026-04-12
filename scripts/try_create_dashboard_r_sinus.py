#!/usr/bin/env python3
from __future__ import annotations

import base64
import json
import os
import sys
from pathlib import Path
from urllib import error, request

import keyring

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from src.arkana_mdd_db.config import get_main_db_config, load_env


def _root_path() -> str:
    load_env()
    return os.getenv("ROOT_PATH", "http://127.0.0.1:8000").rstrip("/")


def _api_username() -> str:
    return os.getenv("ARKANA_API_USER", "root_nf")


def _api_password() -> str:
    load_env()
    username = _api_username()
    password = os.getenv("ARKANA_API_PASSWORD")
    if password:
        return password
    config = get_main_db_config()
    keyring_password = keyring.get_password(config.api_keyring_service, username)
    if keyring_password:
        return keyring_password
    raise RuntimeError(
        f"No API password found for {username}. Set ARKANA_API_PASSWORD or store it in keyring service "
        f"{config.api_keyring_service}."
    )


def _auth_header() -> str:
    token = base64.b64encode(f"{_api_username()}:{_api_password()}".encode("utf-8")).decode("ascii")
    return f"Basic {token}"


def _request(method: str, path: str, payload: dict | None = None) -> dict:
    url = f"{_root_path()}{path}"
    headers = {
        "Authorization": _auth_header(),
        "Accept": "application/json",
    }
    data = None
    if payload is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(payload).encode("utf-8")
    req = request.Request(url=url, data=data, headers=headers, method=method)
    try:
        with request.urlopen(req) as response:
            body = response.read().decode("utf-8")
            return json.loads(body) if body else {}
    except error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"{method} {url} failed with {exc.code}: {body}") from exc


def main() -> None:
    create_payload = {
        "object_key": "board_r_sinus_test",
        "description": "API test board for R sinus graphic",
        "cells": [
            {
                "cell_key": "intro",
                "cell_type": "text",
                "content": "R sinus test board",
            },
            {
                "cell_key": "sinus_r",
                "cell_type": "r_code",
                "content": (
                    'png("sinus.png", width=900, height=600); '
                    "x <- seq(0, 2*pi, length.out=300); "
                    "y <- sin(x); "
                    'plot(x, y, type="l", lwd=3, col="steelblue", '
                    'main="Sinus", xlab="x", ylab="sin(x)"); '
                    "grid(); "
                    "dev.off()"
                ),
            },
        ],
    }

    created_board = _request("POST", "/report", create_payload)
    arkana_id = int(created_board["arkana_id"])

    run_result = _request("POST", f"/report/{arkana_id}/cell/sinus_r/run?save=true")
    files_result = _request("GET", f"/report/{arkana_id}/files")

    print("created_board:")
    print(json.dumps(created_board, indent=2))
    print()
    print("run_result:")
    print(json.dumps(run_result, indent=2))
    print()
    print("files:")
    print(json.dumps(files_result, indent=2))


if __name__ == "__main__":
    main()
