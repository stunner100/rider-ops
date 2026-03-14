"""
Data ingestion module: validate, clean, deduplicate, and append rider order data.
"""
import os
from datetime import datetime
from typing import Any

import pandas as pd

try:
    import psycopg
    from psycopg import sql
    from psycopg.rows import dict_row
    from psycopg.types.json import Jsonb
except Exception:  # pragma: no cover
    psycopg = None
    sql = None
    dict_row = None
    Jsonb = None

from config import (
    COLUMN_ALIASES,
    DATA_DIR,
    DATABASE_MASTER_TABLE,
    DATABASE_UPLOAD_LOG_TABLE,
    DATABASE_URL,
    MASTER_COLLECTION_FIELDS,
    MASTER_FILE,
    REQUIRED_COLUMNS,
    UPLOAD_LOG_COLLECTION_FIELDS,
    UPLOAD_LOG_FILE,
)


_DATABASE_SCHEMA_READY = False


def ensure_data_dir():
    """Create the data directory if it doesn't exist."""
    os.makedirs(DATA_DIR, exist_ok=True)


def _normalize_column_name(name: str) -> str:
    """Normalize column headers so alias matching tolerates case and spacing noise."""
    return " ".join(str(name).strip().lower().split())


def _database_enabled() -> bool:
    return bool(DATABASE_URL and psycopg)


def _db_connect(**kwargs):
    if not _database_enabled():
        raise RuntimeError("DATABASE_URL is not configured.")
    return psycopg.connect(DATABASE_URL, **kwargs)


def _database_identifier(name: str):
    return sql.Identifier(name)


def _database_columns(names: list[str]):
    return sql.SQL(", ").join(_database_identifier(name) for name in names)


def _ensure_database_schema():
    global _DATABASE_SCHEMA_READY
    if _DATABASE_SCHEMA_READY or not _database_enabled():
        return

    with _db_connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                sql.SQL(
                    """
                    CREATE TABLE IF NOT EXISTS {} (
                        order_id TEXT PRIMARY KEY,
                        order_datetime TIMESTAMP NOT NULL,
                        rider_name TEXT NOT NULL,
                        order_status TEXT NOT NULL,
                        dispatch_time TIMESTAMP NULL,
                        pickup_time TIMESTAMP NULL,
                        delivered_time TIMESTAMP NULL,
                        dispatched_at TIMESTAMP NULL,
                        delivered_at TIMESTAMP NULL,
                        vendor TEXT NULL,
                        zone TEXT NULL,
                        cancellation_reason TEXT NULL,
                        meta JSONB NULL,
                        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    )
                    """
                ).format(_database_identifier(DATABASE_MASTER_TABLE))
            )
            cur.execute(
                sql.SQL("CREATE INDEX IF NOT EXISTS {} ON {} (order_datetime)").format(
                    _database_identifier(f"{DATABASE_MASTER_TABLE}_order_datetime_idx"),
                    _database_identifier(DATABASE_MASTER_TABLE),
                )
            )
            cur.execute(
                sql.SQL(
                    """
                    CREATE TABLE IF NOT EXISTS {} (
                        id BIGSERIAL PRIMARY KEY,
                        timestamp TIMESTAMP NOT NULL,
                        filename TEXT NOT NULL,
                        rows_in_file INTEGER NOT NULL,
                        rows_after_cleaning INTEGER NOT NULL,
                        rows_dropped_during_cleaning INTEGER NOT NULL,
                        rows_added INTEGER NOT NULL,
                        duplicates_removed INTEGER NOT NULL,
                        total_master_rows INTEGER NOT NULL,
                        errors TEXT NULL,
                        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    )
                    """
                ).format(_database_identifier(DATABASE_UPLOAD_LOG_TABLE))
            )
            cur.execute(
                sql.SQL("CREATE INDEX IF NOT EXISTS {} ON {} (timestamp DESC)").format(
                    _database_identifier(f"{DATABASE_UPLOAD_LOG_TABLE}_timestamp_idx"),
                    _database_identifier(DATABASE_UPLOAD_LOG_TABLE),
                )
            )

    _DATABASE_SCHEMA_READY = True


def _is_missing_value(value: Any) -> bool:
    try:
        result = pd.isna(value)
    except TypeError:
        return False
    return bool(result)


def _clean_sql_value(value: Any) -> Any:
    if _is_missing_value(value):
        return None
    if isinstance(value, pd.Timestamp):
        return value.to_pydatetime()
    return value


def _clean_json_value(value: Any) -> Any:
    if _is_missing_value(value):
        return None
    if isinstance(value, pd.Timestamp):
        return value.to_pydatetime().isoformat()
    if isinstance(value, datetime):
        return value.isoformat()
    return value


def _row_to_record(row: dict, allowed_fields: list[str] | None = None) -> dict:
    allowed_set = set(allowed_fields) if allowed_fields else None
    payload = {}
    extras = {}

    for key, value in row.items():
        if allowed_set is not None and key not in allowed_set:
            extras[key] = _clean_json_value(value)
            continue
        payload[key] = _clean_sql_value(value)

    if allowed_set is not None and "meta" in allowed_set:
        payload["meta"] = {k: v for k, v in extras.items() if v is not None} or None

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


def _load_master_from_database() -> pd.DataFrame:
    if not _database_enabled():
        return _load_master_csv()

    _ensure_database_schema()
    with _db_connect(row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute(
                sql.SQL("SELECT {} FROM {} ORDER BY order_datetime ASC").format(
                    _database_columns(MASTER_COLLECTION_FIELDS),
                    _database_identifier(DATABASE_MASTER_TABLE),
                )
            )
            records = cur.fetchall()

    if not records:
        return pd.DataFrame()

    df = pd.DataFrame(records)
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


def _log_upload_to_database(entry: dict):
    if not _database_enabled():
        return

    _ensure_database_schema()
    with _db_connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                sql.SQL(
                    """
                    INSERT INTO {} (
                        timestamp,
                        filename,
                        rows_in_file,
                        rows_after_cleaning,
                        rows_dropped_during_cleaning,
                        rows_added,
                        duplicates_removed,
                        total_master_rows,
                        errors
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """
                ).format(_database_identifier(DATABASE_UPLOAD_LOG_TABLE)),
                (
                    _clean_sql_value(entry.get("timestamp")),
                    entry.get("filename"),
                    entry.get("rows_in_file", 0),
                    entry.get("rows_after_cleaning", 0),
                    entry.get("rows_dropped_during_cleaning", 0),
                    entry.get("rows_added", 0),
                    entry.get("duplicates_removed", 0),
                    entry.get("total_master_rows", 0),
                    entry.get("errors", ""),
                ),
            )


def map_columns(df: pd.DataFrame) -> dict:
    """
    Rename columns in `df` from raw export headers to internal standardized names
    using COLUMN_ALIASES. Mutates `df` in place.

    Returns a result dict:
        {
            "mapped": {original_name: internal_name, ...},
            "unmapped_required": [internal_name, ...],
            "extra": [col_name, ...],
        }
    """
    file_columns = list(df.columns)
    normalized_columns = {}
    for col in file_columns:
        normalized_columns.setdefault(_normalize_column_name(col), col)
    rename_map = {}
    resolved = set()

    for internal_name, aliases in COLUMN_ALIASES.items():
        for alias in aliases:
            matched_col = normalized_columns.get(_normalize_column_name(alias))
            if matched_col and internal_name not in resolved:
                rename_map[matched_col] = internal_name
                resolved.add(internal_name)
                break

    if rename_map:
        df.rename(columns=rename_map, inplace=True)

    df.columns = [str(col).strip() for col in df.columns]

    unmapped_required = [c for c in REQUIRED_COLUMNS if c not in df.columns]
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
        for col in REQUIRED_COLUMNS:
            null_count = df[col].isna().sum()
            if null_count > 0:
                warnings.append(f"Column '{col}' has {null_count} null value(s).")

    return {"valid": len(errors) == 0, "errors": errors, "warnings": warnings}


def clean_data(df: pd.DataFrame, return_stats: bool = False):
    """Normalize values, coerce timestamps, and optionally report cleaning losses."""
    df = df.copy()
    original_count = len(df)

    df.columns = [str(c).strip() for c in df.columns]

    if "order_id" in df.columns:
        order_ids = df["order_id"].where(df["order_id"].notna(), "").astype(str).str.strip()
        order_ids = order_ids.str.replace(r"\.0+$", "", regex=True)
        df["order_id"] = order_ids.replace("", pd.NA)

    if "rider_name" in df.columns:
        rider_names = df["rider_name"].where(df["rider_name"].notna(), "").astype(str).str.strip().str.title()
        df["rider_name"] = rider_names.replace("", pd.NA)

    if "order_datetime" in df.columns:
        df["order_datetime"] = pd.to_datetime(df["order_datetime"], errors="coerce")

    for col in ["dispatch_time", "pickup_time", "delivered_time", "dispatched_at", "delivered_at"]:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce")

    if "order_status" in df.columns:
        statuses = df["order_status"].where(df["order_status"].notna(), "").astype(str).str.strip().str.title()
        df["order_status"] = statuses.replace("", pd.NA)

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

    new_df = new_df.drop_duplicates(subset=["order_id"], keep="first")

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
    """Load the master orders dataset from Postgres when configured."""
    if _database_enabled():
        try:
            return _load_master_from_database()
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

    if _database_enabled() and not clean_new.empty:
        _ensure_database_schema()
        insert_sql = sql.SQL(
            """
            INSERT INTO {} (
                order_id,
                order_datetime,
                rider_name,
                order_status,
                dispatch_time,
                pickup_time,
                delivered_time,
                dispatched_at,
                delivered_at,
                vendor,
                zone,
                cancellation_reason,
                meta
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (order_id) DO NOTHING
            """
        ).format(_database_identifier(DATABASE_MASTER_TABLE))

        with _db_connect() as conn:
            with conn.cursor() as cur:
                for row in clean_new.to_dict(orient="records"):
                    payload = _row_to_record(row, allowed_fields=MASTER_COLLECTION_FIELDS)
                    cur.execute(
                        insert_sql,
                        (
                            payload.get("order_id"),
                            payload.get("order_datetime"),
                            payload.get("rider_name"),
                            payload.get("order_status"),
                            payload.get("dispatch_time"),
                            payload.get("pickup_time"),
                            payload.get("delivered_time"),
                            payload.get("dispatched_at"),
                            payload.get("delivered_at"),
                            payload.get("vendor"),
                            payload.get("zone"),
                            payload.get("cancellation_reason"),
                            Jsonb(payload["meta"]) if payload.get("meta") is not None else None,
                        ),
                    )
                    rows_added += max(cur.rowcount, 0)
    elif not clean_new.empty:
        if master_df.empty:
            combined = clean_new.copy()
        else:
            combined = pd.concat([master_df, clean_new], ignore_index=True)
        _save_master_csv(combined)
        rows_added = len(clean_new)

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
    """Log an upload event to Postgres when configured, otherwise CSV."""
    timestamp = datetime.now()
    entry = {
        "timestamp": timestamp,
        "filename": filename,
        "rows_in_file": stats.get("original_count", 0),
        "rows_after_cleaning": stats.get("cleaned_count", 0),
        "rows_dropped_during_cleaning": stats.get("rows_dropped_during_cleaning", 0),
        "rows_added": stats.get("rows_added", 0),
        "duplicates_removed": stats.get("duplicates_removed", 0),
        "total_master_rows": stats.get("total_rows", 0),
        "errors": "; ".join(stats.get("errors", [])),
    }
    if _database_enabled():
        try:
            _log_upload_to_database(entry)
            return
        except Exception:
            pass

    ensure_data_dir()
    csv_entry = dict(entry)
    csv_entry["timestamp"] = timestamp.strftime("%Y-%m-%d %H:%M:%S")
    entry_df = pd.DataFrame([csv_entry])
    if os.path.exists(UPLOAD_LOG_FILE):
        log_df = pd.read_csv(UPLOAD_LOG_FILE)
        log_df = pd.concat([log_df, entry_df], ignore_index=True)
    else:
        log_df = entry_df
    _save_upload_log_csv(log_df)


def load_upload_log() -> pd.DataFrame:
    """Load the upload log, or return empty DataFrame."""
    if _database_enabled():
        try:
            _ensure_database_schema()
            with _db_connect(row_factory=dict_row) as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        sql.SQL("SELECT {} FROM {} ORDER BY timestamp DESC").format(
                            _database_columns(UPLOAD_LOG_COLLECTION_FIELDS),
                            _database_identifier(DATABASE_UPLOAD_LOG_TABLE),
                        )
                    )
                    records = cur.fetchall()
            if records:
                df = pd.DataFrame(records)
                if "timestamp" in df.columns:
                    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce").dt.strftime("%Y-%m-%d %H:%M:%S")
                return df
            return pd.DataFrame()
        except Exception:
            return _load_upload_log_csv()
    return _load_upload_log_csv()
