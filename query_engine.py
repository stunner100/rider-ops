"""
Natural-language query engine for rider operations.
Uses keyword-based pattern matching to answer common staffing questions.
"""
import re
import pandas as pd
from config import WEEKDAY_NAMES, SHIFT_ORDER
from rider_profiling import compute_rider_profiles, get_rider_detail, _assign_shift
from demand_analysis import orders_by_shift, orders_by_weekday, get_demand_summary


def query(question: str, df: pd.DataFrame) -> dict:
    """
    Parse a plain-English question and return an answer.
    Returns: {
        "answer": str,
        "table": DataFrame or None,
        "chart_type": str or None,  # "bar", "line", "table"
        "filters": str,
    }
    """
    q = question.lower().strip()

    # Extract time-related tokens
    weekday_filter = _extract_weekday(q)
    shift_filter = _extract_shift(q)
    rider_names = _extract_rider_names(q, df)
    n = _extract_number(q)

    profiles = compute_rider_profiles(df)

    # ── Route to handlers ───────────────────────────────────────────
    if _matches(q, ["top", "best", "reliable", "most reliable"]) and _matches(q, ["rider"]):
        return _top_riders(profiles, n or 10, weekday_filter, shift_filter, q)

    if _matches(q, ["worst", "least", "weakest", "lowest"]) and _matches(q, ["rider"]):
        return _bottom_riders(profiles, n or 10, q)

    if _matches(q, ["compare"]) and len(rider_names) >= 2:
        return _compare_riders(profiles, rider_names)

    if rider_names and len(rider_names) == 1:
        return _rider_info(profiles, rider_names[0], df)

    if _matches(q, ["how many rider", "riders needed", "riders do i need", "need for"]):
        return _riders_needed(df, weekday_filter, shift_filter)

    if weekday_filter and _matches(q, ["rider", "who", "work", "works", "working"]):
        return _riders_by_weekday(profiles, df, weekday_filter, shift_filter, n or 10, q)

    if _matches(q, ["evening", "night", "lunch", "morning", "afternoon"]) and _matches(q, ["rider", "who"]):
        shift = _extract_shift(q)
        return _riders_by_shift(profiles, df, shift)

    if _matches(q, ["declining", "reduced", "dropping", "decreasing", "less active"]):
        return _declining_riders(profiles, n or 10)

    if _matches(q, ["increasing", "growing", "improving", "more active"]):
        return _improving_riders(profiles, n or 10)

    if _matches(q, ["inactive", "not working", "absent", "missing"]):
        return _inactive_riders(profiles)

    if _matches(q, ["at least", "minimum", "more than"]) and _matches(q, ["day", "week", "order"]):
        return _threshold_riders(profiles, q)

    if _matches(q, ["demand", "busiest", "peak", "orders by"]):
        return _demand_overview(df, weekday_filter, shift_filter)

    if _matches(q, ["category", "categories", "core", "backup", "at-risk", "flexible"]):
        return _riders_by_category(profiles, q)

    # Fallback
    return {
        "answer": "I couldn't understand that question. Try asking about top riders, shift coverage, demand patterns, or specific rider performance.",
        "table": None,
        "chart_type": None,
        "filters": f"Question: {question}",
    }


# ── Handler Functions ─────────────────────────────────────────────────────────

def _top_riders(profiles, n, weekday, shift, q):
    sort_col = "total_orders"
    if _matches(q, ["attendance", "consistent", "reliability"]):
        sort_col = "attendance_consistency"
    elif _matches(q, ["productivity", "orders per day", "efficient"]):
        sort_col = "avg_orders_per_day"
    elif _matches(q, ["completion", "delivered"]):
        sort_col = "completion_rate"

    result = profiles.nlargest(n, sort_col)[
        ["rider_name", "category", "total_orders", "avg_orders_per_day",
         "attendance_consistency", "completion_rate", "preferred_shift"]
    ]

    filters = f"Sorted by: {sort_col}"
    if weekday:
        filters += f" | Weekday: {weekday}"
    if shift:
        filters += f" | Shift: {shift}"

    return {
        "answer": f"Here are the top {len(result)} riders by {sort_col.replace('_', ' ')}:",
        "table": result,
        "chart_type": "bar",
        "filters": filters,
    }


def _bottom_riders(profiles, n, q):
    sort_col = "total_orders"
    if _matches(q, ["attendance"]):
        sort_col = "attendance_consistency"
    elif _matches(q, ["completion"]):
        sort_col = "completion_rate"

    result = profiles.nsmallest(n, sort_col)[
        ["rider_name", "category", "total_orders", "avg_orders_per_day",
         "attendance_consistency", "completion_rate"]
    ]

    return {
        "answer": f"Here are the bottom {len(result)} riders by {sort_col.replace('_', ' ')}:",
        "table": result,
        "chart_type": "bar",
        "filters": f"Sorted by: {sort_col} (ascending)",
    }


def _compare_riders(profiles, rider_names):
    mask = profiles["rider_name"].str.lower().isin([r.lower() for r in rider_names])
    result = profiles[mask][
        ["rider_name", "category", "total_orders", "delivered_orders",
         "avg_orders_per_day", "attendance_consistency", "completion_rate",
         "preferred_shift", "preferred_weekday", "recent_trend"]
    ]

    if result.empty:
        return {
            "answer": f"Could not find riders: {', '.join(rider_names)}",
            "table": None, "chart_type": None, "filters": "",
        }

    return {
        "answer": f"Comparison of {' vs '.join(result['rider_name'].tolist())}:",
        "table": result,
        "chart_type": "table",
        "filters": f"Riders: {', '.join(rider_names)}",
    }


def _rider_info(profiles, rider_name, df):
    mask = profiles["rider_name"].str.lower() == rider_name.lower()
    if not mask.any():
        return {"answer": f"Rider '{rider_name}' not found.", "table": None, "chart_type": None, "filters": ""}

    rider = profiles[mask].iloc[0]
    answer = (
        f"**{rider['rider_name']}** ({rider['category']})\n\n"
        f"- Total Orders: {rider['total_orders']} | Delivered: {rider['delivered_orders']}\n"
        f"- Completion Rate: {rider['completion_rate']}%\n"
        f"- Active Days: {rider['active_days']} | Avg Orders/Day: {rider['avg_orders_per_day']}\n"
        f"- Preferred Shift: {rider['preferred_shift']} | Preferred Day: {rider['preferred_weekday']}\n"
        f"- Attendance: {rider['attendance_consistency']}% | Trend: {rider['recent_trend']}\n"
    )

    return {
        "answer": answer,
        "table": profiles[mask][["rider_name", "category", "total_orders", "avg_orders_per_day",
                                  "attendance_consistency", "completion_rate", "preferred_shift",
                                  "recent_trend"]],
        "chart_type": "table",
        "filters": f"Rider: {rider_name}",
    }


def _riders_needed(df, weekday, shift):
    from deployment_engine import estimate_riders_needed
    needs = estimate_riders_needed(df)

    if weekday:
        needs = needs[needs["weekday"] == weekday]
    if shift:
        needs = needs[needs["shift"] == shift]

    if needs.empty:
        return {"answer": "No data for the specified filters.", "table": None, "chart_type": None, "filters": ""}

    total = needs["riders_needed"].sum()
    filters = []
    if weekday:
        filters.append(f"Weekday: {weekday}")
    if shift:
        filters.append(f"Shift: {shift}")

    return {
        "answer": f"Estimated riders needed: **{total}** total across the selected slots.",
        "table": needs[["weekday", "shift", "avg_orders", "riders_needed"]],
        "chart_type": "bar",
        "filters": " | ".join(filters) if filters else "All days and shifts",
    }


def _riders_by_shift(profiles, df, shift):
    if not shift:
        shift = "Lunch"
    result = profiles[profiles["preferred_shift"] == shift].nlargest(10, "total_orders")[
        ["rider_name", "category", "total_orders", "avg_orders_per_day",
         "preferred_shift", "attendance_consistency"]
    ]

    return {
        "answer": f"Top riders who prefer the **{shift}** shift:",
        "table": result,
        "chart_type": "bar",
        "filters": f"Shift filter: {shift}",
    }


def _riders_by_weekday(profiles, df, weekday, shift, n, q):
    activity = df.copy()
    activity["order_datetime"] = pd.to_datetime(activity["order_datetime"], errors="coerce")
    activity = activity.dropna(subset=["order_datetime", "rider_name"])
    activity["weekday"] = activity["order_datetime"].dt.day_name()
    activity["shift"] = activity["order_datetime"].dt.hour.apply(_assign_shift)

    filtered = activity[activity["weekday"] == weekday]
    if shift:
        filtered = filtered[filtered["shift"] == shift]

    if filtered.empty:
        filters = [f"Weekday: {weekday}"]
        if shift:
            filters.append(f"Shift: {shift}")
        return {
            "answer": "No rider activity matched that day filter.",
            "table": None,
            "chart_type": None,
            "filters": " | ".join(filters),
        }

    rider_summary = filtered.groupby("rider_name").agg(
        matching_orders=("rider_name", "size"),
        active_dates=("order_datetime", lambda s: s.dt.date.nunique()),
    ).reset_index()

    total_orders = activity.groupby("rider_name").size().reset_index(name="total_orders")
    rider_summary = rider_summary.merge(total_orders, on="rider_name", how="left")
    rider_summary["share_of_orders_pct"] = (
        rider_summary["matching_orders"] / rider_summary["total_orders"].clip(lower=1) * 100
    ).round(1)

    rider_summary = rider_summary.merge(
        profiles[
            [
                "rider_name",
                "category",
                "preferred_weekday",
                "preferred_shift",
                "attendance_consistency",
                "avg_orders_per_day",
            ]
        ],
        on="rider_name",
        how="left",
    )

    if _matches(q, ["mostly", "mainly", "usually", "typically"]):
        sort_cols = ["share_of_orders_pct", "matching_orders"]
        ascending = [False, False]
    else:
        sort_cols = ["matching_orders", "share_of_orders_pct"]
        ascending = [False, False]

    result = rider_summary.sort_values(sort_cols, ascending=ascending).head(n)[
        [
            "rider_name",
            "category",
            "matching_orders",
            "active_dates",
            "share_of_orders_pct",
            "avg_orders_per_day",
            "preferred_weekday",
            "preferred_shift",
            "attendance_consistency",
        ]
    ]

    filters = [f"Weekday: {weekday}"]
    if shift:
        filters.append(f"Shift: {shift}")

    answer = f"Here are the riders most active on **{weekday}**"
    if shift:
        answer += f" during the **{shift}** shift"
    answer += ":"

    return {
        "answer": answer,
        "table": result,
        "chart_type": "bar",
        "filters": " | ".join(filters),
    }


def _declining_riders(profiles, n):
    declining = profiles[profiles["recent_trend_pct"] < -10].nsmallest(n, "recent_trend_pct")[
        ["rider_name", "category", "total_orders", "recent_trend_pct", "recent_trend",
         "days_since_last_active"]
    ]

    return {
        "answer": f"Riders with declining activity (last 14 days vs prior 14 days):",
        "table": declining if not declining.empty else None,
        "chart_type": "bar",
        "filters": "Trend window: 14 days",
    }


def _improving_riders(profiles, n):
    improving = profiles[profiles["recent_trend_pct"] > 10].nlargest(n, "recent_trend_pct")[
        ["rider_name", "category", "total_orders", "recent_trend_pct", "recent_trend"]
    ]

    return {
        "answer": f"Riders with increasing activity:",
        "table": improving if not improving.empty else None,
        "chart_type": "bar",
        "filters": "Trend window: 14 days",
    }


def _inactive_riders(profiles):
    inactive = profiles[profiles["category"] == "Inactive"][
        ["rider_name", "total_orders", "days_since_last_active", "last_active_date"]
    ]

    return {
        "answer": f"Found **{len(inactive)}** inactive rider(s) (no activity in last 14 days):",
        "table": inactive if not inactive.empty else None,
        "chart_type": "table",
        "filters": "Inactive threshold: 14 days",
    }


def _threshold_riders(profiles, q):
    # Try to parse: "at least X days" and "average above Y orders"
    days_match = re.search(r"(\d+)\s*days?\s*(per\s*week|a\s*week)?", q)
    orders_match = re.search(r"(above|more than|over|at least)\s*(\d+)\s*orders?", q)

    filtered = profiles.copy()
    filters = []

    if days_match:
        min_days = int(days_match.group(1))
        # Convert days/week to total active days (approx: active_days / active_weeks)
        filtered["days_per_week"] = (filtered["active_days"] / filtered["active_weeks"].clip(lower=1)).round(1)
        filtered = filtered[filtered["days_per_week"] >= min_days]
        filters.append(f"Min days/week: {min_days}")

    if orders_match:
        min_orders = int(orders_match.group(2))
        filtered = filtered[filtered["avg_orders_per_day"] >= min_orders]
        filters.append(f"Min avg orders/day: {min_orders}")

    cols = ["rider_name", "category", "active_days", "active_weeks",
            "avg_orders_per_day", "attendance_consistency"]
    if "days_per_week" in filtered.columns:
        cols.insert(3, "days_per_week")

    return {
        "answer": f"Found **{len(filtered)}** rider(s) matching your criteria:",
        "table": filtered[cols] if not filtered.empty else None,
        "chart_type": "table",
        "filters": " | ".join(filters) if filters else "Custom threshold query",
    }


def _demand_overview(df, weekday, shift):
    summary = get_demand_summary(df)
    by_shift = orders_by_shift(df)

    if shift:
        by_shift = by_shift[by_shift["shift"] == shift]

    answer = (
        f"**Demand Overview**\n\n"
        f"- Total Orders: {summary['total_orders']:,}\n"
        f"- Delivered: {summary['delivered_orders']:,} ({summary['completion_rate']}%)\n"
        f"- Active Riders: {summary['unique_riders']}\n"
        f"- Avg Daily Orders: {summary['avg_daily_orders']}\n"
    )

    return {
        "answer": answer,
        "table": by_shift,
        "chart_type": "bar",
        "filters": f"Shift: {shift}" if shift else "All shifts",
    }


def _riders_by_category(profiles, q):
    cat = None
    for c in ["Core", "Peak", "Flexible", "Backup", "At-risk", "Inactive"]:
        if c.lower() in q:
            cat = c
            break

    if cat:
        result = profiles[profiles["category"] == cat]
    else:
        result = profiles

    table = result[["rider_name", "category", "total_orders", "avg_orders_per_day",
                     "attendance_consistency", "completion_rate"]].copy()

    cat_counts = profiles["category"].value_counts()

    return {
        "answer": f"Rider categories: {dict(cat_counts)}" + (f"\n\nShowing **{cat}** riders:" if cat else ""),
        "table": table,
        "chart_type": "bar",
        "filters": f"Category: {cat}" if cat else "All categories",
    }


# ── Helper Extractors ─────────────────────────────────────────────────────────

def _matches(text: str, keywords: list) -> bool:
    return any(kw in text for kw in keywords)


def _extract_weekday(text: str) -> str:
    for day in WEEKDAY_NAMES:
        if day.lower() in text:
            return day
    return None


def _extract_shift(text: str) -> str:
    for shift in SHIFT_ORDER:
        if shift.lower() in text:
            return shift
    return None


def _extract_number(text: str) -> int:
    match = re.search(r"\b(top|best|worst|bottom)\s+(\d+)", text)
    if match:
        return int(match.group(2))
    match = re.search(r"(\d+)\s+(rider|best|top|worst)", text)
    if match:
        return int(match.group(1))
    return None


def _normalize_search_text(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(text).lower()).strip()


def _extract_rider_names(text: str, df: pd.DataFrame) -> list:
    """Try to find rider names mentioned in the query."""
    riders = [
        rider for rider in df["rider_name"].dropna().astype(str).unique()
        if rider.strip()
    ]
    if not riders:
        return []

    normalized_text = f" {_normalize_search_text(text)} "
    exact_matches = []

    for rider in riders:
        normalized_rider = _normalize_search_text(rider)
        if normalized_rider and f" {normalized_rider} " in normalized_text:
            exact_matches.append(rider)

    if exact_matches:
        return exact_matches

    first_name_matches = []
    first_name_to_riders = {}
    for rider in riders:
        normalized_rider = _normalize_search_text(rider)
        if not normalized_rider:
            continue
        first_name = normalized_rider.split()[0]
        if len(first_name) <= 3:
            continue
        first_name_to_riders.setdefault(first_name, set()).add(rider)

    for token in normalized_text.split():
        matched_riders = first_name_to_riders.get(token, set())
        if len(matched_riders) == 1:
            first_name_matches.extend(matched_riders)

    seen = set()
    deduped_matches = []
    for rider in first_name_matches:
        if rider not in seen:
            seen.add(rider)
            deduped_matches.append(rider)

    return deduped_matches
