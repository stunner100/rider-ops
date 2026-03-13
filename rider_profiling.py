"""
Rider profiling engine: compute metrics, classify riders, generate profiles.
"""
import pandas as pd
import numpy as np
from config import (
    SHIFT_BUCKETS, SHIFT_ORDER, WEEKDAY_NAMES,
    INACTIVE_DAYS_THRESHOLD, RECENT_TREND_WINDOW_DAYS,
)


def _assign_shift(hour: int) -> str:
    """Map an hour (0-23) to a shift bucket name."""
    for shift, (start, end) in SHIFT_BUCKETS.items():
        if shift == "Night":
            if hour >= start or hour < end:
                return shift
        else:
            if start <= hour < end:
                return shift
    return "Unknown"


def compute_rider_profiles(df: pd.DataFrame) -> pd.DataFrame:
    """
    Compute per-rider profile metrics from the master orders DataFrame.
    Returns a DataFrame with one row per rider.
    """
    if df.empty:
        return pd.DataFrame()

    df = df.copy()
    df["order_datetime"] = pd.to_datetime(df["order_datetime"], errors="coerce")
    df = df.dropna(subset=["order_datetime"])
    df["date"] = df["order_datetime"].dt.date
    df["hour"] = df["order_datetime"].dt.hour
    df["weekday"] = df["order_datetime"].dt.day_name()
    df["shift"] = df["hour"].apply(_assign_shift)

    today = df["order_datetime"].max().normalize()
    recent_cutoff = today - pd.Timedelta(days=RECENT_TREND_WINDOW_DAYS)

    profiles = []

    for rider, rdf in df.groupby("rider_name"):
        total_orders = len(rdf)
        delivered = len(rdf[rdf["order_status"] == "Delivered"])
        completion_rate = round(delivered / total_orders * 100, 1) if total_orders > 0 else 0

        active_dates = rdf["date"].nunique()
        active_weeks = rdf["order_datetime"].dt.isocalendar().week.nunique()

        avg_orders_per_day = round(total_orders / max(active_dates, 1), 1)

        # Active hours: diff between first and last order each day
        daily_spans = rdf.groupby("date")["hour"].agg(["min", "max"])
        daily_spans["span"] = daily_spans["max"] - daily_spans["min"] + 1
        avg_hours_per_day = round(daily_spans["span"].mean(), 1)
        avg_orders_per_hour = round(total_orders / max(daily_spans["span"].sum(), 1), 1)

        avg_first_hour = round(daily_spans["min"].mean(), 1)
        avg_last_hour = round(daily_spans["max"].mean(), 1)

        # Preferred shift and weekday
        preferred_shift = rdf["shift"].mode().iloc[0] if not rdf["shift"].mode().empty else "Unknown"
        preferred_weekday = rdf["weekday"].mode().iloc[0] if not rdf["weekday"].mode().empty else "Unknown"

        # Attendance consistency: active_dates / total possible days in range
        date_range = (rdf["date"].max() - rdf["date"].min()).days + 1
        attendance_consistency = round(active_dates / max(date_range, 1) * 100, 1)

        # Recent trend: orders in recent window vs prior window
        recent_orders = len(rdf[rdf["order_datetime"] >= recent_cutoff])
        prior_cutoff = recent_cutoff - pd.Timedelta(days=RECENT_TREND_WINDOW_DAYS)
        prior_orders = len(rdf[(rdf["order_datetime"] >= prior_cutoff) & (rdf["order_datetime"] < recent_cutoff)])

        if prior_orders > 0:
            trend_pct = round((recent_orders - prior_orders) / prior_orders * 100, 1)
        elif recent_orders > 0:
            trend_pct = 100.0
        else:
            trend_pct = 0.0

        if trend_pct > 10:
            trend_label = "↑ Increasing"
        elif trend_pct < -10:
            trend_label = "↓ Declining"
        else:
            trend_label = "→ Stable"

        # Days since last activity
        last_active = rdf["order_datetime"].max()
        days_since_last = (today - last_active).days

        profiles.append({
            "rider_name": rider,
            "total_orders": total_orders,
            "delivered_orders": delivered,
            "completion_rate": completion_rate,
            "active_days": active_dates,
            "active_weeks": active_weeks,
            "avg_orders_per_day": avg_orders_per_day,
            "avg_hours_per_day": avg_hours_per_day,
            "avg_orders_per_hour": avg_orders_per_hour,
            "avg_first_hour": avg_first_hour,
            "avg_last_hour": avg_last_hour,
            "preferred_shift": preferred_shift,
            "preferred_weekday": preferred_weekday,
            "attendance_consistency": attendance_consistency,
            "recent_trend_pct": trend_pct,
            "recent_trend": trend_label,
            "days_since_last_active": days_since_last,
            "last_active_date": last_active.strftime("%Y-%m-%d"),
        })

    profiles_df = pd.DataFrame(profiles)
    profiles_df["category"] = profiles_df.apply(classify_rider, axis=1)
    return profiles_df.sort_values("total_orders", ascending=False).reset_index(drop=True)


def classify_rider(row) -> str:
    """Classify a rider into a category based on their profile metrics."""
    if row["days_since_last_active"] > INACTIVE_DAYS_THRESHOLD:
        return "Inactive"
    if row["recent_trend_pct"] < -30 or row["completion_rate"] < 60:
        return "At-risk"
    if row["attendance_consistency"] >= 70 and row["avg_orders_per_day"] >= 10:
        return "Core"
    if row["preferred_shift"] in ["Lunch", "Evening"] and row["avg_orders_per_day"] >= 7:
        return "Peak"
    if row["active_days"] <= 8 and row["completion_rate"] >= 70:
        return "Backup"
    return "Flexible"


def get_rider_detail(rider_name: str, df: pd.DataFrame) -> dict:
    """
    Get detailed data for a single rider.
    Returns dict with daily_orders, hourly_distribution, weekday_orders, shift_orders.
    """
    rdf = df[df["rider_name"] == rider_name].copy()
    if rdf.empty:
        return {}

    rdf["order_datetime"] = pd.to_datetime(rdf["order_datetime"], errors="coerce")
    rdf["date"] = rdf["order_datetime"].dt.date
    rdf["hour"] = rdf["order_datetime"].dt.hour
    rdf["weekday"] = rdf["order_datetime"].dt.day_name()
    rdf["shift"] = rdf["hour"].apply(_assign_shift)

    daily_orders = rdf.groupby("date").size().reset_index(name="orders")
    daily_orders["date"] = pd.to_datetime(daily_orders["date"])

    hourly_dist = rdf.groupby("hour").size().reset_index(name="orders")

    weekday_orders = rdf.groupby("weekday").size().reindex(WEEKDAY_NAMES, fill_value=0).reset_index()
    weekday_orders.columns = ["weekday", "orders"]

    shift_orders = rdf.groupby("shift").size().reindex(SHIFT_ORDER, fill_value=0).reset_index()
    shift_orders.columns = ["shift", "orders"]

    status_dist = rdf["order_status"].value_counts().reset_index()
    status_dist.columns = ["status", "count"]

    return {
        "daily_orders": daily_orders,
        "hourly_distribution": hourly_dist,
        "weekday_orders": weekday_orders,
        "shift_orders": shift_orders,
        "status_distribution": status_dist,
        "total_records": len(rdf),
    }
