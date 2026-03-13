"""
Demand analysis module: aggregate orders by day, hour, shift, weekday.
"""
import pandas as pd
import numpy as np
from config import SHIFT_BUCKETS, SHIFT_ORDER, WEEKDAY_NAMES


def _assign_shift(hour: int) -> str:
    for shift, (start, end) in SHIFT_BUCKETS.items():
        if shift == "Night":
            if hour >= start or hour < end:
                return shift
        else:
            if start <= hour < end:
                return shift
    return "Unknown"


def _prepare(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["order_datetime"] = pd.to_datetime(df["order_datetime"], errors="coerce")
    df = df.dropna(subset=["order_datetime"])
    df["date"] = df["order_datetime"].dt.date
    df["hour"] = df["order_datetime"].dt.hour
    df["weekday"] = df["order_datetime"].dt.day_name()
    df["shift"] = df["hour"].apply(_assign_shift)
    return df


def orders_by_day(df: pd.DataFrame) -> pd.DataFrame:
    """Total and delivered orders per calendar date."""
    df = _prepare(df)
    total = df.groupby("date").size().reset_index(name="total_orders")
    delivered = df[df["order_status"] == "Delivered"].groupby("date").size().reset_index(name="delivered_orders")
    result = total.merge(delivered, on="date", how="left").fillna(0)
    result["date"] = pd.to_datetime(result["date"])
    result["delivered_orders"] = result["delivered_orders"].astype(int)
    return result.sort_values("date")


def orders_by_weekday(df: pd.DataFrame) -> pd.DataFrame:
    """Average orders per weekday."""
    df = _prepare(df)
    daily = df.groupby(["date", "weekday"]).size().reset_index(name="orders")
    avg = daily.groupby("weekday")["orders"].mean().reindex(WEEKDAY_NAMES).reset_index()
    avg.columns = ["weekday", "avg_orders"]
    avg["avg_orders"] = avg["avg_orders"].round(1)
    return avg


def orders_by_hour(df: pd.DataFrame) -> pd.DataFrame:
    """Average orders per hour of day."""
    df = _prepare(df)
    daily_hourly = df.groupby(["date", "hour"]).size().reset_index(name="orders")
    num_days = df["date"].nunique()
    avg = daily_hourly.groupby("hour")["orders"].sum().reset_index()
    avg["avg_orders"] = (avg["orders"] / max(num_days, 1)).round(1)
    return avg[["hour", "avg_orders"]]


def orders_by_shift(df: pd.DataFrame) -> pd.DataFrame:
    """Total and average orders per shift bucket."""
    df = _prepare(df)
    num_days = df["date"].nunique()
    total = df.groupby("shift").size().reindex(SHIFT_ORDER, fill_value=0).reset_index()
    total.columns = ["shift", "total_orders"]
    total["avg_orders_per_day"] = (total["total_orders"] / max(num_days, 1)).round(1)
    return total


def active_riders_by_day(df: pd.DataFrame) -> pd.DataFrame:
    """Number of unique active riders per day."""
    df = _prepare(df)
    result = df.groupby("date")["rider_name"].nunique().reset_index(name="active_riders")
    result["date"] = pd.to_datetime(result["date"])
    return result.sort_values("date")


def orders_per_rider_per_day(df: pd.DataFrame) -> pd.DataFrame:
    """Average orders per rider per day."""
    df = _prepare(df)
    daily = df.groupby(["date", "rider_name"]).size().reset_index(name="orders")
    avg = daily.groupby("date")["orders"].mean().reset_index(name="avg_orders_per_rider")
    avg["date"] = pd.to_datetime(avg["date"])
    avg["avg_orders_per_rider"] = avg["avg_orders_per_rider"].round(1)
    return avg.sort_values("date")


def demand_heatmap_data(df: pd.DataFrame) -> pd.DataFrame:
    """
    Weekday × Shift matrix of average orders.
    Returns a pivotable DataFrame.
    """
    df = _prepare(df)
    daily = df.groupby(["date", "weekday", "shift"]).size().reset_index(name="orders")
    avg = daily.groupby(["weekday", "shift"])["orders"].mean().reset_index(name="avg_orders")
    avg["avg_orders"] = avg["avg_orders"].round(1)

    # Pivot for heatmap
    pivot = avg.pivot(index="weekday", columns="shift", values="avg_orders")
    pivot = pivot.reindex(index=WEEKDAY_NAMES, columns=SHIFT_ORDER, fill_value=0)
    return pivot


def peak_demand_windows(df: pd.DataFrame, top_n: int = 5) -> pd.DataFrame:
    """Top N weekday-shift combinations by average order volume."""
    df = _prepare(df)
    daily = df.groupby(["date", "weekday", "shift"]).size().reset_index(name="orders")
    avg = daily.groupby(["weekday", "shift"])["orders"].mean().reset_index(name="avg_orders")
    avg["avg_orders"] = avg["avg_orders"].round(1)
    return avg.nlargest(top_n, "avg_orders").reset_index(drop=True)


def get_demand_summary(df: pd.DataFrame) -> dict:
    """Return a summary dict of key demand metrics."""
    df = _prepare(df)
    total_orders = len(df)
    delivered = len(df[df["order_status"] == "Delivered"])
    unique_riders = df["rider_name"].nunique()
    date_range_days = df["date"].nunique()
    avg_daily_orders = round(total_orders / max(date_range_days, 1), 1)
    avg_daily_riders = round(df.groupby("date")["rider_name"].nunique().mean(), 1)
    completion_rate = round(delivered / max(total_orders, 1) * 100, 1)

    return {
        "total_orders": total_orders,
        "delivered_orders": delivered,
        "unique_riders": unique_riders,
        "date_range_days": date_range_days,
        "avg_daily_orders": avg_daily_orders,
        "avg_daily_riders": avg_daily_riders,
        "completion_rate": completion_rate,
    }
