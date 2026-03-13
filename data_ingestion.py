"""
Data ingestion module: validate, clean, deduplicate, and append rider order data.
"""
import pandas as pd
from datetime import datetime
import os
from typing import Any
try:
    import requests
except Exception:  # pragma: no cover
    requests = None

from config import (
    REQUIRED_COLUMNS, DATA_DIR, MASTER_FILE, UPLOAD_LOG_FILE, COLUMN_ALIASES,
    POCKETBASE_URL, POCKETBASE_API_TOKEN, POCKETBASE_MASTER_COLLECTION,
    POCKETBASE_UPLOAD_LOG_COLLECTION, POCKETBASE_PAGE_SIZE, MASTER_COLLECTION_FIELDS,
    POCKETBASE_ADMIN_EMAIL, POCKETBASE_ADMIN_PASSWORD,
)


def ensure_data_dir():
    """Create the data directory if it doesn't exist."""
    os.makedirs(DATA_DIR, exist_ok=True)


def _normalize_column_name(name: str) -> str:
    """Normalize column headers so alias matching tolerates case and spacing noise."""
    return " ".join(str(name).strip().lower().split())


def _pocketbase_enabled() -> bool:
    has_token = bool(POCKETBASE_API_TOKEN)
    has_login = bool(POCKETBASE_ADMIN_EMAIL and POCKETBASE_ADMIN_PASSWORD)
    return bool(POCKETBASE_URL and requests and (has_token or has_login))


_POCKETBASE_RUNTIME_TOKEN = None


def _pocketbase_token() -> str:
    global _POCKETBASE_RUNTIME_TOKEN
    if POCKETBASE_API_TOKEN:
        return POCKETBASE_API_TOKEN
    if _POCKETBASE_RUNTIME_TOKEN:
        return _POCKETBASE_RUNTIME_TOKEN

    if not POCKETBASE_ADMIN_EMAIL or not POCKETBASE_ADMIN_PASSWORD:
        raise RuntimeError(
            "PocketBase is configured without POCKETBASE_API_TOKEN. Set POCKETBASE_ADMIN_EMAIL and POCKETBASE_ADMIN_PASSWORD."
        )

    response = requests.post(
        f"{POCKETBASE_URL.rstrip('/')}/api/collections/_superusers/auth-with-password",
        headers={"Content-Type": "application/json"},
        json={
            "identity": POCKETBASE_ADMIN_EMAIL,
            "password": POCKETBASE_ADMIN_PASSWORD,
        },
        timeout=20,
    )
    if response.status_code >= 400:
        raise RuntimeError(
            f"PocketBase superuser auth failed ({response.status_code}): {response.text}"
        )
    token = response.json().get("token")
    if not token:
        raise RuntimeError("PocketBase superuser auth response did not include token.")
    _POCKETBASE_RUNTIME_TOKEN = token
    return token


def _clear_pocketbase_token():
    global _POCKETBASE_RUNTIME_TOKEN
    _POCKETBASE_RUNTIME_TOKEN = None


def _pocketbase_headers():
    return {
        "Authorization": f"Bearer {_pocketbase_token()}",
        "Content-Type": "application/json",
    }


def _pocketbase_url(path: str) -> str:
    return f"{POCKETBASE_URL.rstrip('/')}/{path.lstrip('/')}"


def _pocketbase_request(method: str, path: str, params: dict = None, json_body=None) -> Any:
    if not _pocketbase_enabled():
        raise RuntimeError("PocketBase is not configured.")

    last_error = None
    for _ in range(2):
        response = requests.request(
            method=method,
            url=_pocketbase_url(path),
            headers=_pocketbase_headers(),
            params=params,
            json=json_body,
            timeout=20,
        )
        if response.status_code != 401:
            return response

        # If token expired and we can re-auth with admin credentials, retry once with a new token.
        if POCKETBASE_ADMIN_EMAIL and POCKETBASE_ADMIN_PASSWORD:
            _clear_pocketbase_token()
            last_error = response
            continue
        return response

    return last_error


def _pocketbase_request_data(method: str, path: str, params: dict = None, json_body=None) -> dict:
    response = _pocketbase_request(method, path, params=params, json_body=json_body)
    if response.status_code >= 400:
        detail = response.text.strip() if response.text else "No response body"
        raise RuntimeError(f"PocketBase request failed ({response.status_code}) {path}: {detail}")
    if not response.text:
        return {}
    return response.json()


def _pocketbase_fetch_all_records(collection: str, extra_params: dict = None) -> list:
    if not _pocketbase_enabled():
        return []

    page = 1
    records = []

    while True:
        params = {
            "page": page,
            "perPage": POCKETBASE_PAGE_SIZE,
        }
        if extra_params:
            params.update(extra_params)

        try:
            data = _pocketbase_request_data("GET", f"api/collections/{collection}/records", params=params)
        except Exception:
            raise

        items = data.get("items", [])
        if not items:
            break

        records.extend(items)

        total_pages = data.get("totalPages")
        if total_pages is not None and page >= int(total_pages):
            break
        if len(items) < POCKETBASE_PAGE_SIZE:
            break
        page += 1

    return records


def _clean_payload_value(value):
    if pd.isna(value):
        return None
    if isinstance(value, pd.Timestamp):
        return value.to_pydatetime().isoformat()
    if isinstance(value, datetime):
        return value.isoformat()
    return value


def _row_to_payload(row: pd.Series, allowed_fields: list = None) -> dict:
    allowed_set = set(allowed_fields) if allowed_fields else None
    payload = {}
    extras = {}
    for key, value in row.items():
        if key in {"id", "collectionId", "collectionName", "created", "updated", "expand"}:
            continue
        if allowed_set is not None and key not in allowed_set:
            extras[key] = _clean_payload_value(value)
            continue
        payload[key] = _clean_payload_value(value)

    # Preserve any unknown upload columns in an optional JSON field.
    if allowed_set is not None and "meta" in allowed_set:
        payload["meta"] = extras or None

    return payload


def _save_master_csv(df: pd.DataFrame):
    ensure_data_dir()
    df.to_csv(MASTER_FILE, index=False)


def _load_master_csv() -> pd.DataFrame:
    ensure_data_dir()
    if not os.path.exists(MASTER_FILE):
        return pd.DataFrame()

    df = pd.read_csv(MASTER_FILE, parse_dates=["order_datetime"])
    for col in ["dispatch_time", "pickup_time", "delivered_time", "dispatched_at", "delivered_at"]:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce")
    return df


def _load_master_from_pocketbase() -> pd.DataFrame:
    if not _pocketbase_enabled():
        return _load_master_csv()

    records = _pocketbase_fetch_all_records(
        POCKETBASE_MASTER_COLLECTION,
        extra_params={"fields": "*,created,updated"},
    )
    if not records:
        return pd.DataFrame()

    df = pd.DataFrame(records)
    for col in ["id", "collectionId", "collectionName", "created", "updated", "expand"]:
        if col in df.columns:
            df = df.drop(columns=[col])

    if "order_datetime" in df.columns:
        df["order_datetime"] = pd.to_datetime(df["order_datetime"], errors="coerce")
    for col in ["dispatch_time", "pickup_time", "delivered_time", "dispatched_at", "delivered_at"]:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce")

    return df


def _save_upload_log_csv(df: pd.DataFrame):
    ensure_data_dir()
    df.to_csv(UPLOAD_LOG_FILE, index=False)


def _load_upload_log_csv() -> pd.DataFrame:
    if os.path.exists(UPLOAD_LOG_FILE):
        return pd.read_csv(UPLOAD_LOG_FILE)
    return pd.DataFrame()


def _log_upload_to_pocketbase(entry: dict):
    if not _pocketbase_enabled():
        return

    _pocketbase_request_data(
        "POST",
        f"api/collections/{POCKETBASE_UPLOAD_LOG_COLLECTION}/records",
        json_body=entry,
    )


def map_columns(df: pd.DataFrame) -> dict:
    """
    Rename columns in `df` from raw export headers to internal standardized names
    using COLUMN_ALIASES. Mutates `df` in place.

    Returns a result dict:
        {
            "mapped": {original_name: internal_name, ...},
            "unmapped_required": [internal_name, ...],   # required fields with no alias found
            "extra": [col_name, ...],                     # columns left unchanged
        }
    """
    file_columns = list(df.columns)
    normalized_columns = {}
    for col in file_columns:
        normalized_columns.setdefault(_normalize_column_name(col), col)
    rename_map = {}        # {original_col -> internal_name}
    resolved = set()       # set of internal names that have been matched

    for internal_name, aliases in COLUMN_ALIASES.items():
        for alias in aliases:
            matched_col = normalized_columns.get(_normalize_column_name(alias))
            if matched_col and internal_name not in resolved:
                rename_map[matched_col] = internal_name
                resolved.add(internal_name)
                break

    # Apply the renames
    if rename_map:
        df.rename(columns=rename_map, inplace=True)

    # Strip whitespace from remaining column names so downstream validation is consistent.
    df.columns = [str(col).strip() for col in df.columns]

    # Figure out which required columns are still missing after mapping
    unmapped_required = [c for c in REQUIRED_COLUMNS if c not in df.columns]

    # Columns that weren't mapped and aren't known internal names
    all_internal = set(COLUMN_ALIASES.keys())
    extra = [c for c in df.columns if c not in all_internal]

    return {
        "mapped": rename_map,
        "unmapped_required": unmapped_required,
        "extra": extra,
    }


def validate_csv(df: pd.DataFrame) -> dict:
    """
    Validate uploaded DataFrame has required columns.
    Should be called AFTER map_columns() so columns are already standardized.
    Returns {"valid": bool, "errors": [...], "warnings": [...]}.
    """
    errors = []
    warnings = []

    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        errors.append(f"Missing required columns: {', '.join(missing)}")

    if df.empty:
        errors.append("File contains no data rows.")

    if not errors:
        # Check for nulls in required cols
        for col in REQUIRED_COLUMNS:
            null_count = df[col].isna().sum()
            if null_count > 0:
                warnings.append(f"Column '{col}' has {null_count} null value(s).")

    return {"valid": len(errors) == 0, "errors": errors, "warnings": warnings}


def clean_data(df: pd.DataFrame, return_stats: bool = False):
    """Normalize values, coerce timestamps, and optionally report cleaning losses."""
    df = df.copy()
    original_count = len(df)

    # Lightly normalize any remaining non-standard column names
    # (map_columns already handles known aliases; this catches stragglers)
    df.columns = [str(c).strip() for c in df.columns]

    if "order_id" in df.columns:
        order_ids = df["order_id"].where(df["order_id"].notna(), "").astype(str).str.strip()
        order_ids = order_ids.str.replace(r"\.0+$", "", regex=True)
        df["order_id"] = order_ids.replace("", pd.NA)

    # Normalize rider names
    if "rider_name" in df.columns:
        rider_names = df["rider_name"].where(df["rider_name"].notna(), "").astype(str).str.strip().str.title()
        df["rider_name"] = rider_names.replace("", pd.NA)

    # Parse order_datetime
    if "order_datetime" in df.columns:
        df["order_datetime"] = pd.to_datetime(df["order_datetime"], errors="coerce")

    # Parse optional timestamp columns (support both old and alias-mapped names)
    for col in ["dispatch_time", "pickup_time", "delivered_time",
                "dispatched_at", "delivered_at"]:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce")

    # Standardize order_status
    if "order_status" in df.columns:
        statuses = df["order_status"].where(df["order_status"].notna(), "").astype(str).str.strip().str.title()
        df["order_status"] = statuses.replace("", pd.NA)

    # Drop rows where required fields are null after cleaning
    df = df.dropna(subset=["order_id", "order_datetime", "rider_name", "order_status"])

    if not return_stats:
        return df

    return {
        "clean_df": df,
        "original_count": original_count,
        "cleaned_count": len(df),
        "rows_dropped_during_cleaning": original_count - len(df),
    }


def deduplicate(new_df: pd.DataFrame, master_df: pd.DataFrame = None) -> dict:
    """
    Remove duplicates within new_df and against master_df.
    Returns {"clean_df": DataFrame, "duplicates_removed": int, "original_count": int}.
    """
    original_count = len(new_df)

    # Internal dedup
    new_df = new_df.drop_duplicates(subset=["order_id"], keep="first")

    # Cross-dedup against master
    if master_df is not None and not master_df.empty:
        existing_ids = set(master_df["order_id"].astype(str).values)
        new_df = new_df[~new_df["order_id"].astype(str).isin(existing_ids)]

    duplicates_removed = original_count - len(new_df)
    return {
        "clean_df": new_df,
        "duplicates_removed": duplicates_removed,
        "original_count": original_count,
    }


def load_master() -> pd.DataFrame:
    """Load the master orders dataset, from PocketBase when configured."""
    if _pocketbase_enabled():
        try:
            return _load_master_from_pocketbase()
        except Exception:
            return _load_master_csv()

    return _load_master_csv()


def append_to_master(new_df: pd.DataFrame, original_count: int = None) -> dict:
    """
    Append new data to the master dataset.
    Returns stats: {rows_added, duplicates_removed, total_rows, original_count}.
    """
    master_df = load_master()
    dedup_result = deduplicate(new_df, master_df)
    clean_new = dedup_result["clean_df"]
    rows_added = 0

    if _pocketbase_enabled() and not clean_new.empty:
        for row in clean_new.to_dict(orient="records"):
            try:
                _pocketbase_request_data(
                    "POST",
                    f"api/collections/{POCKETBASE_MASTER_COLLECTION}/records",
                    json_body=_row_to_payload(pd.Series(row), allowed_fields=MASTER_COLLECTION_FIELDS),
                )
                rows_added += 1
            except Exception as exc:
                error_text = str(exc).lower()
                if "unique" in error_text and "order_id" in error_text:
                    continue
                raise
    elif not clean_new.empty:
        if master_df.empty:
            combined = clean_new.copy()
        else:
            combined = pd.concat([master_df, clean_new], ignore_index=True)
        _save_master_csv(combined)
        rows_added = len(clean_new)
    else:
        rows_added = 0

    if not _pocketbase_enabled():
        combined = pd.concat([master_df, clean_new], ignore_index=True) if not clean_new.empty else master_df

    return {
        "rows_added": rows_added,
        "duplicates_removed": dedup_result["duplicates_removed"],
        "total_rows": len(master_df) + rows_added,
        "original_count": original_count if original_count is not None else dedup_result["original_count"],
        "cleaned_count": dedup_result["original_count"],
        "rows_dropped_during_cleaning": max(
            (original_count if original_count is not None else dedup_result["original_count"])
            - dedup_result["original_count"],
            0,
        ),
    }


def log_upload(filename: str, stats: dict):
    """Log an upload event to the upload log CSV."""
    entry = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "filename": filename,
        "rows_in_file": stats.get("original_count", 0),
        "rows_after_cleaning": stats.get("cleaned_count", 0),
        "rows_dropped_during_cleaning": stats.get("rows_dropped_during_cleaning", 0),
        "rows_added": stats.get("rows_added", 0),
        "duplicates_removed": stats.get("duplicates_removed", 0),
        "total_master_rows": stats.get("total_rows", 0),
        "errors": "; ".join(stats.get("errors", [])),
    }
    if _pocketbase_enabled():
        try:
            _log_upload_to_pocketbase(entry)
            return
        except Exception:
            pass

    ensure_data_dir()
    entry_df = pd.DataFrame([entry])
    if os.path.exists(UPLOAD_LOG_FILE):
        log_df = pd.read_csv(UPLOAD_LOG_FILE)
        log_df = pd.concat([log_df, entry_df], ignore_index=True)
    else:
        log_df = entry_df
    _save_upload_log_csv(log_df)


def load_upload_log() -> pd.DataFrame:
    """Load the upload log, or return empty DataFrame."""
    if _pocketbase_enabled():
        try:
            records = _pocketbase_fetch_all_records(
                POCKETBASE_UPLOAD_LOG_COLLECTION,
                extra_params={"fields": "timestamp,filename,rows_in_file,rows_after_cleaning,rows_dropped_during_cleaning,rows_added,duplicates_removed,total_master_rows,errors"},
            )
            if records:
                df = pd.DataFrame(records)
                for col in ["id", "collectionId", "collectionName", "created", "updated", "expand"]:
                    if col in df.columns:
                        df = df.drop(columns=[col])
                return df
            return pd.DataFrame()
        except Exception:
            return _load_upload_log_csv()
    return pd.DataFrame()
