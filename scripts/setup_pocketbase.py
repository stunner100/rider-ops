#!/usr/bin/env python3
"""
Bootstrap required PocketBase collections for Rider Ops.

Usage:
    python scripts/setup_pocketbase.py
"""
import sys
from typing import Any, Dict, List

import requests

from config import (
    POCKETBASE_URL,
    POCKETBASE_API_TOKEN,
    POCKETBASE_ADMIN_TOKEN,
    POCKETBASE_ADMIN_EMAIL,
    POCKETBASE_ADMIN_PASSWORD,
    POCKETBASE_MASTER_COLLECTION,
    POCKETBASE_UPLOAD_LOG_COLLECTION,
)


def _headers(token: str) -> Dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }


def _request(method: str, url: str, token: str, **kwargs):
    response = requests.request(method=method, url=url, headers=_headers(token), timeout=20, **kwargs)
    return response


def _auth_token() -> str:
    if POCKETBASE_API_TOKEN:
        return POCKETBASE_API_TOKEN
    if POCKETBASE_ADMIN_TOKEN:
        return POCKETBASE_ADMIN_TOKEN

    if not POCKETBASE_ADMIN_EMAIL or not POCKETBASE_ADMIN_PASSWORD:
        raise RuntimeError(
            "No token found. Set POCKETBASE_API_TOKEN or POCKETBASE_ADMIN_EMAIL/POCKETBASE_ADMIN_PASSWORD."
        )

    response = requests.post(
        f"{POCKETBASE_URL.rstrip('/')}/api/collections/_superusers/auth-with-password",
        json={
            "identity": POCKETBASE_ADMIN_EMAIL,
            "password": POCKETBASE_ADMIN_PASSWORD,
        },
        timeout=20,
    )
    if response.status_code >= 300:
        raise RuntimeError(f"Admin auth failed ({response.status_code}): {response.text}")

    return response.json()["token"]


def _field_text(name: str, required: bool = False) -> Dict[str, Any]:
    return {
        "name": name,
        "type": "text",
        "required": required,
        "system": False,
        "options": {"min": None, "max": None, "pattern": ""},
    }


def _field_json(name: str, required: bool = False) -> Dict[str, Any]:
    return {
        "name": name,
        "type": "json",
        "required": required,
        "system": False,
        "options": {},
    }


def _ensure_collection(token: str, name: str, schema: List[Dict[str, Any]], indexes: List[str] = None):
    if indexes is None:
        indexes = []

    exists = _request(
        "GET",
        f"{POCKETBASE_URL.rstrip('/')}/api/collections",
        token,
    )
    if exists.status_code >= 300:
        raise RuntimeError(f"Failed to list collections ({exists.status_code}): {exists.text}")

    existing = {item.get("name") for item in exists.json().get("items", [])}
    if name in existing:
        print(f"Collection exists: {name}")
        return

    payload = {
        "name": name,
        "type": "base",
        "schema": schema,
        "indexes": indexes,
    }
    created = _request(
        "POST",
        f"{POCKETBASE_URL.rstrip('/')}/api/collections",
        token,
        json=payload,
    )
    if created.status_code >= 300:
        raise RuntimeError(f"Failed to create {name} ({created.status_code}): {created.text}")

    print(f"Created collection: {name}")


def main() -> int:
    if not POCKETBASE_URL:
        print("POCKETBASE_URL is required", file=sys.stderr)
        return 1

    token = _auth_token()

    master_schema = [
        _field_text("order_id", required=True),
        _field_text("order_datetime", required=True),
        _field_text("rider_name", required=True),
        _field_text("order_status", required=True),
        _field_text("dispatch_time"),
        _field_text("pickup_time"),
        _field_text("delivered_time"),
        _field_text("dispatched_at"),
        _field_text("delivered_at"),
        _field_text("vendor"),
        _field_text("zone"),
        _field_text("cancellation_reason"),
        _field_json("meta"),
    ]
    _ensure_collection(
        token,
        POCKETBASE_MASTER_COLLECTION,
        master_schema,
    )

    log_schema = [
        _field_text("timestamp", required=True),
        _field_text("filename"),
        _field_text("rows_in_file"),
        _field_text("rows_after_cleaning"),
        _field_text("rows_dropped_during_cleaning"),
        _field_text("rows_added"),
        _field_text("duplicates_removed"),
        _field_text("total_master_rows"),
        _field_text("errors"),
    ]
    _ensure_collection(
        token,
        POCKETBASE_UPLOAD_LOG_COLLECTION,
        log_schema,
    )

    print("PocketBase collections ready.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
