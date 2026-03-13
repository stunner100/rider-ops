#!/usr/bin/env python3
"""
Refresh POCKETBASE_API_TOKEN and optionally persist it into .env.

Usage:
  python scripts/refresh_pocketbase_token.py
  python scripts/refresh_pocketbase_token.py --force
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import re
from datetime import datetime, timedelta, timezone
from datetime import datetime, timezone
from pathlib import Path

import requests
from dotenv import load_dotenv


def _env_path(env_file: str | None) -> Path:
    return Path(env_file).expanduser() if env_file else Path(".env")


def _read_env(path: Path) -> dict[str, str]:
    env = {}
    if not path.exists():
        return env

    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        env[key.strip()] = value.strip()
    return env


def _load_config(path: Path) -> tuple[str, str, str]:
    load_dotenv(path, override=False)
    base_url = os.getenv("POCKETBASE_URL", "").strip()
    email = os.getenv("POCKETBASE_ADMIN_EMAIL", "").strip()
    password = os.getenv("POCKETBASE_ADMIN_PASSWORD", "").strip()
    return base_url, email, password


def _jwt_expiry(token: str) -> datetime | None:
    try:
        payload_b64 = token.split(".")[1]
        padded = payload_b64 + "=" * (-len(payload_b64) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded.encode()).decode())
        exp = payload.get("exp")
        if isinstance(exp, int):
            return datetime.fromtimestamp(exp, tz=timezone.utc)
    except Exception:
        return None
    return None


def _is_token_valid(token: str, buffer_seconds: int = 300) -> bool:
    if not token:
        return False
    expiry = _jwt_expiry(token)
    if not expiry:
        # Unknown expiry format => be permissive and reuse token
        return True
    now = datetime.now(timezone.utc)
    return expiry > (now + timedelta(seconds=buffer_seconds))


def _issue_token(base_url: str, email: str, password: str) -> str:
    if not base_url:
        raise RuntimeError("POCKETBASE_URL is required.")
    if not email or not password:
        raise RuntimeError("POCKETBASE_ADMIN_EMAIL and POCKETBASE_ADMIN_PASSWORD are required.")

    response = requests.post(
        f"{base_url.rstrip('/')}/api/collections/_superusers/auth-with-password",
        headers={"Content-Type": "application/json"},
        json={"identity": email, "password": password},
        timeout=20,
    )
    if response.status_code >= 400:
        raise RuntimeError(f"Superuser auth failed ({response.status_code}): {response.text}")
    token = response.json().get("token")
    if not token:
        raise RuntimeError("Auth response did not include token.")
    return token


def _write_env_token(path: Path, token: str, variable_name: str = "POCKETBASE_API_TOKEN"):
    existing = path.read_text() if path.exists() else ""
    pattern = re.compile(rf"^{re.escape(variable_name)}=.*$", re.MULTILINE)
    replacement = f"{variable_name}={token}"

    if pattern.search(existing):
        updated = pattern.sub(replacement, existing)
    else:
        newline = "\n" if existing and not existing.endswith("\n") else ""
        updated = existing + newline + replacement + "\n"

    path.write_text(updated)


def main():
    parser = argparse.ArgumentParser(description="Refresh PocketBase API token.")
    parser.add_argument("--env-file", default=".env", help="Path to env file (default: .env)")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Always create a fresh token, even if existing token is still valid."
    )
    parser.add_argument(
        "--no-store",
        action="store_true",
        help="Do not write token back to env file; only print it."
    )
    parser.add_argument(
        "--buffer-seconds",
        type=int,
        default=300,
        help="Treat token as expired this many seconds before actual expiry (default 300).",
    )

    args = parser.parse_args()
    env_path = _env_path(args.env_file)
    config = _read_env(env_path)
    # Support inline token in environment when running from shell.
    existing_token = os.getenv("POCKETBASE_API_TOKEN") or config.get("POCKETBASE_API_TOKEN", "")

    url, email, password = _load_config(env_path)
    needs_refresh = args.force or not _is_token_valid(existing_token, args.buffer_seconds)

    if needs_refresh:
        new_token = _issue_token(url, email, password)
        if args.no_store:
            print(new_token)
            return
        _write_env_token(env_path, new_token)
        print(new_token)
    else:
        print(existing_token)


if __name__ == "__main__":
    main()
