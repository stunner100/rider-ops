"""
Executive Dashboard — KPIs, trends, peak analysis.
"""
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from data_ingestion import load_master
from demand_analysis import (
    orders_by_day, orders_by_weekday, orders_by_hour,
    orders_by_shift, active_riders_by_day, orders_per_rider_per_day,
    get_demand_summary, peak_demand_windows,
)
from styles import apply_custom_css, PLOT_LAYOUT

st.set_page_config(page_title="Executive Dashboard", page_icon="📊", layout="wide")
apply_custom_css()

st.markdown("## 📊 Executive Dashboard")
st.caption("High-level operational KPIs, order trends, and peak demand analysis")

df = load_master()
if df.empty:
    st.warning("⚠️ No data available. Please upload data first via the **Upload Data** page.")
    st.stop()

summary = get_demand_summary(df)

# ─── KPI Cards ────────────────────────────────────────────────────────────────
c1, c2, c3, c4 = st.columns(4)
kpis = [
    ("Total Orders", f"{summary['total_orders']:,}", "purple", f"{summary['date_range_days']} days"),
    ("Delivered", f"{summary['delivered_orders']:,}", "green", f"{summary['completion_rate']}% completion"),
    ("Active Riders", f"{summary['unique_riders']}", "blue", f"Avg {summary['avg_daily_riders']}/day"),
    ("Avg Daily Orders", f"{summary['avg_daily_orders']}", "orange", f"{summary['avg_daily_riders']} avg riders"),
]

for col, (label, value, color, sub) in zip([c1, c2, c3, c4], kpis):
    col.markdown(f"""
    <div class="kpi-card {color}">
        <div class="kpi-label">{label}</div>
        <div class="kpi-value {color}">{value}</div>
        <div class="kpi-sublabel">{sub}</div>
    </div>
    """, unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# ─── Order Trend ──────────────────────────────────────────────────────────────
tab1, tab2 = st.tabs(["📈 Order Trends", "📊 Peak Analysis"])

with tab1:
    col_left, col_right = st.columns([3, 2])

    with col_left:
        daily = orders_by_day(df)
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=daily["date"], y=daily["total_orders"],
            mode="lines+markers", name="Total Orders",
            line=dict(color="#a29bfe", width=2.5),
            marker=dict(size=5),
            fill="tozeroy", fillcolor="rgba(162, 155, 254, 0.1)"
        ))
        fig.add_trace(go.Scatter(
            x=daily["date"], y=daily["delivered_orders"],
            mode="lines+markers", name="Delivered",
            line=dict(color="#55efc4", width=2),
            marker=dict(size=4),
        ))
        fig.update_layout(**PLOT_LAYOUT, title="Daily Order Volume", height=380,
                          legend=dict(orientation="h", yanchor="bottom", y=1.02))
        st.plotly_chart(fig, use_container_width=True)

    with col_right:
        riders_daily = active_riders_by_day(df)
        fig2 = go.Figure()
        fig2.add_trace(go.Bar(
            x=riders_daily["date"], y=riders_daily["active_riders"],
            marker_color="#74b9ff", marker_line_width=0,
            opacity=0.8,
        ))
        fig2.update_layout(**PLOT_LAYOUT, title="Active Riders Per Day", height=380)
        st.plotly_chart(fig2, use_container_width=True)

    # Orders per rider per day
    opr = orders_per_rider_per_day(df)
    fig3 = go.Figure()
    fig3.add_trace(go.Scatter(
        x=opr["date"], y=opr["avg_orders_per_rider"],
        mode="lines+markers", name="Avg Orders/Rider",
        line=dict(color="#fdcb6e", width=2.5),
        marker=dict(size=5),
        fill="tozeroy", fillcolor="rgba(253, 203, 110, 0.1)"
    ))
    fig3.update_layout(**PLOT_LAYOUT, title="Average Orders Per Rider Per Day", height=300)
    st.plotly_chart(fig3, use_container_width=True)


with tab2:
    col_a, col_b = st.columns(2)

    with col_a:
        by_weekday = orders_by_weekday(df)
        fig4 = go.Figure()
        colors = ["#6c5ce7" if v == by_weekday["avg_orders"].max() else "#a29bfe"
                  for v in by_weekday["avg_orders"]]
        fig4.add_trace(go.Bar(
            x=by_weekday["weekday"], y=by_weekday["avg_orders"],
            marker_color=colors, marker_line_width=0,
        ))
        fig4.update_layout(**PLOT_LAYOUT, title="Average Orders by Weekday", height=350)
        st.plotly_chart(fig4, use_container_width=True)

    with col_b:
        by_shift = orders_by_shift(df)
        fig5 = go.Figure()
        shift_colors = {"Morning": "#74b9ff", "Lunch": "#fdcb6e", "Afternoon": "#55efc4",
                        "Evening": "#a29bfe", "Night": "#636e72"}
        fig5.add_trace(go.Bar(
            x=by_shift["shift"], y=by_shift["avg_orders_per_day"],
            marker_color=[shift_colors.get(s, "#a29bfe") for s in by_shift["shift"]],
            marker_line_width=0,
        ))
        fig5.update_layout(**PLOT_LAYOUT, title="Average Orders by Shift", height=350)
        st.plotly_chart(fig5, use_container_width=True)

    # Hourly distribution
    by_hour = orders_by_hour(df)
    fig6 = go.Figure()
    fig6.add_trace(go.Scatter(
        x=by_hour["hour"], y=by_hour["avg_orders"],
        mode="lines+markers",
        line=dict(color="#e17055", width=2.5),
        marker=dict(size=6),
        fill="tozeroy", fillcolor="rgba(225, 112, 85, 0.1)"
    ))
    fig6.update_layout(**PLOT_LAYOUT, title="Average Orders by Hour of Day", height=300,
                       xaxis_title="Hour (0-23)", yaxis_title="Avg Orders")
    st.plotly_chart(fig6, use_container_width=True)

    # Peak demand windows
    st.markdown("### 🔥 Top Peak Demand Windows")
    peaks = peak_demand_windows(df, top_n=8)
    st.dataframe(peaks, use_container_width=True, hide_index=True)
