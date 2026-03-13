"""
Deployment recommendation engine: estimate staffing needs and rank riders per shift.
"""
import pandas as pd
import numpy as np
from config import (
    SHIFT_BUCKETS, SHIFT_ORDER, WEEKDAY_NAMES,
    SCORING_WEIGHTS, DEFAULT_RIDERS_PER_SHIFT,
)


def _assign_shift(hour: int) -> str:
    for shift, (start, end) in SHIFT_BUCKETS.items():
        if shift == "Night":
            if hour >= start or hour < end:
                return shift
        else:
            if start <= hour < end:
                return shift
    return "Unknown"


def estimate_riders_needed(df: pd.DataFrame, avg_productivity: float = None) -> pd.DataFrame:
    """
    Estimate riders needed per weekday per shift based on historical demand.
    If avg_productivity is None, it's computed from data.
    """
    df = df.copy()
    df["order_datetime"] = pd.to_datetime(df["order_datetime"], errors="coerce")
    df = df.dropna(subset=["order_datetime"])
    df["date"] = df["order_datetime"].dt.date
    df["weekday"] = df["order_datetime"].dt.day_name()
    df["hour"] = df["order_datetime"].dt.hour
    df["shift"] = df["hour"].apply(_assign_shift)

    # Compute average productivity if not given
    if avg_productivity is None:
        daily_rider = df.groupby(["date", "rider_name"]).size().reset_index(name="orders")
        avg_productivity = daily_rider["orders"].mean()
        if pd.isna(avg_productivity) or avg_productivity == 0:
            avg_productivity = 10  # fallback

    # Average orders per weekday/shift
    daily = df.groupby(["date", "weekday", "shift"]).size().reset_index(name="orders")
    avg_demand = daily.groupby(["weekday", "shift"])["orders"].mean().reset_index(name="avg_orders")
    avg_demand["avg_orders"] = avg_demand["avg_orders"].round(1)

    # Estimate riders needed (ceil of demand / productivity, min 1)
    avg_demand["riders_needed"] = np.ceil(avg_demand["avg_orders"] / avg_productivity).astype(int)
    avg_demand["riders_needed"] = avg_demand["riders_needed"].clip(lower=1)

    # Reindex for complete grid
    from itertools import product
    full_grid = pd.DataFrame(
        list(product(WEEKDAY_NAMES, SHIFT_ORDER)),
        columns=["weekday", "shift"]
    )
    result = full_grid.merge(avg_demand, on=["weekday", "shift"], how="left").fillna(0)
    result["avg_orders"] = result["avg_orders"].astype(float)
    result["riders_needed"] = result["riders_needed"].astype(int)
    return result


def _score_rider_for_slot(profile: pd.Series, weekday: str, shift: str, df: pd.DataFrame) -> float:
    """
    Score a rider for a specific weekday/shift slot.
    Higher score = better fit.
    """
    score = 0.0
    w = SCORING_WEIGHTS

    # Productivity component (normalized to 0-1, cap at 20 orders/day)
    prod = min(profile.get("avg_orders_per_day", 0) / 20.0, 1.0)
    score += prod * w["productivity"]

    # Attendance consistency (already 0-100)
    att = profile.get("attendance_consistency", 0) / 100.0
    score += att * w["attendance"]

    # Completion rate (already 0-100)
    comp = profile.get("completion_rate", 0) / 100.0
    score += comp * w["completion"]

    # Recency (inversely proportional to days since last active, cap at 30)
    days_ago = profile.get("days_since_last_active", 30)
    recency = max(1.0 - (days_ago / 30.0), 0)
    score += recency * w["recency"]

    # Shift match: check if rider has worked this shift on this weekday before
    rdf = df[(df["rider_name"] == profile["rider_name"])].copy()
    if not rdf.empty:
        rdf["order_datetime"] = pd.to_datetime(rdf["order_datetime"], errors="coerce")
        rdf["hour"] = rdf["order_datetime"].dt.hour
        rdf["weekday"] = rdf["order_datetime"].dt.day_name()
        rdf["shift"] = rdf["hour"].apply(_assign_shift)
        match_orders = len(rdf[(rdf["weekday"] == weekday) & (rdf["shift"] == shift)])
        total_orders = len(rdf)
        shift_match = min(match_orders / max(total_orders, 1) * 5, 1.0)  # scale up
    else:
        shift_match = 0
    score += shift_match * w["shift_match"]

    return round(score * 100, 1)


def rank_riders_for_shift(
    profiles_df: pd.DataFrame, df: pd.DataFrame, weekday: str, shift: str,
    top_n: int = 10
) -> pd.DataFrame:
    """
    Rank riders for a specific weekday/shift, return top N + backups.
    """
    if profiles_df.empty:
        return pd.DataFrame()

    # Exclude inactive riders
    active = profiles_df[profiles_df["category"] != "Inactive"].copy()

    scores = []
    for _, row in active.iterrows():
        s = _score_rider_for_slot(row, weekday, shift, df)
        scores.append({
            "rider_name": row["rider_name"],
            "category": row["category"],
            "score": s,
            "avg_orders_per_day": row["avg_orders_per_day"],
            "attendance_consistency": row["attendance_consistency"],
            "completion_rate": row["completion_rate"],
            "preferred_shift": row["preferred_shift"],
        })

    ranked = pd.DataFrame(scores).sort_values("score", ascending=False).reset_index(drop=True)
    ranked["role"] = ["Primary" if i < top_n else "Backup" for i in range(len(ranked))]
    return ranked


def generate_weekly_plan(profiles_df: pd.DataFrame, df: pd.DataFrame) -> dict:
    """
    Generate a full weekly deployment plan.
    Returns dict: {weekday: {shift: {riders_needed, recommended: DataFrame}}}.
    """
    needs = estimate_riders_needed(df)
    plan = {}

    for weekday in WEEKDAY_NAMES:
        plan[weekday] = {}
        for shift in SHIFT_ORDER:
            row = needs[(needs["weekday"] == weekday) & (needs["shift"] == shift)]
            n_needed = int(row["riders_needed"].values[0]) if len(row) > 0 else DEFAULT_RIDERS_PER_SHIFT
            avg_orders = float(row["avg_orders"].values[0]) if len(row) > 0 else 0

            ranked = rank_riders_for_shift(profiles_df, df, weekday, shift, top_n=n_needed)

            plan[weekday][shift] = {
                "riders_needed": n_needed,
                "avg_orders": avg_orders,
                "recommended": ranked,
            }

    return plan
