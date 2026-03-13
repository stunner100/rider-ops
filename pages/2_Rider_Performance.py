"""
Rider Performance Dashboard — Leaderboard, categories, trends.
"""
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from data_ingestion import load_master
from rider_profiling import compute_rider_profiles
from styles import apply_custom_css, PLOT_LAYOUT

st.set_page_config(page_title="Rider Performance", page_icon="🏆", layout="wide")
apply_custom_css()

st.markdown("## 🏆 Rider Performance")
st.caption("Rider leaderboard, attendance metrics, productivity rankings, and category distribution")

df = load_master()
if df.empty:
    st.warning("⚠️ No data available. Please upload data first.")
    st.stop()

profiles = compute_rider_profiles(df)
if profiles.empty:
    st.info("No rider profiles generated yet.")
    st.stop()

# ─── Category Summary KPIs ───────────────────────────────────────────────────
cat_counts = profiles["category"].value_counts()
cat_colors = {"Core": "purple", "Peak": "green", "Flexible": "blue",
              "Backup": "orange", "At-risk": "orange", "Inactive": "blue"}

cols = st.columns(min(len(cat_counts), 6))
for i, (cat, count) in enumerate(cat_counts.items()):
    color = cat_colors.get(cat, "purple")
    cols[i % len(cols)].markdown(f"""
    <div class="kpi-card {color}" style="padding:16px;">
        <div class="kpi-label">{cat}</div>
        <div class="kpi-value {color}">{count}</div>
        <div class="kpi-sublabel">riders</div>
    </div>
    """, unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# ─── Filters ────────────────────────────────────────────────────────────────
filter_col1, filter_col2, filter_col3 = st.columns([2, 2, 2])

with filter_col1:
    selected_cats = st.multiselect("Filter by Category", options=profiles["category"].unique().tolist(),
                                    default=profiles["category"].unique().tolist())
with filter_col2:
    sort_by = st.selectbox("Sort by", options=[
        "total_orders", "avg_orders_per_day", "attendance_consistency",
        "completion_rate", "active_days", "recent_trend_pct"
    ], index=0)
with filter_col3:
    sort_order = st.radio("Order", ["Descending", "Ascending"], horizontal=True)

filtered = profiles[profiles["category"].isin(selected_cats)]
filtered = filtered.sort_values(sort_by, ascending=(sort_order == "Ascending"))

# ─── Leaderboard ──────────────────────────────────────────────────────────────
st.markdown("### 📋 Rider Leaderboard")

display = filtered.copy()
display.insert(0, "rank", range(1, len(display) + 1))

display_cols = ["rank", "rider_name", "category", "total_orders", "delivered_orders",
                "avg_orders_per_day", "attendance_consistency", "completion_rate",
                "preferred_shift", "recent_trend"]

st.dataframe(
    display[display_cols],
    use_container_width=True,
    hide_index=True,
    height=min(len(display) * 40 + 40, 600),
    column_config={
        "rank": st.column_config.NumberColumn("🏅", width="small"),
        "rider_name": st.column_config.TextColumn("Rider Name", width="medium"),
        "category": st.column_config.TextColumn("Category", width="small"),
        "total_orders": st.column_config.NumberColumn("Total Orders", format="%d"),
        "delivered_orders": st.column_config.NumberColumn("Delivered", format="%d"),
        "avg_orders_per_day": st.column_config.NumberColumn("Avg/Day", format="%.1f"),
        "attendance_consistency": st.column_config.ProgressColumn(
            "Attendance %", format="%.0f%%", min_value=0, max_value=100
        ),
        "completion_rate": st.column_config.ProgressColumn(
            "Completion %", format="%.0f%%", min_value=0, max_value=100
        ),
        "preferred_shift": st.column_config.TextColumn("Pref Shift", width="small"),
        "recent_trend": st.column_config.TextColumn("Trend", width="small"),
    }
)

# ─── Charts ───────────────────────────────────────────────────────────────────
st.markdown("<br>", unsafe_allow_html=True)

tab1, tab2, tab3 = st.tabs(["📊 Category Distribution", "📈 Performance Scatter", "🔥 Trend Analysis"])

with tab1:
    col_a, col_b = st.columns(2)
    with col_a:
        fig = px.pie(profiles, names="category", hole=0.5,
                     color="category",
                     color_discrete_map={"Core": "#6c5ce7", "Peak": "#00b894",
                                         "Flexible": "#0984e3", "Backup": "#fdcb6e",
                                         "At-risk": "#e17055", "Inactive": "#636e72"})
        fig.update_layout(**PLOT_LAYOUT, title="Rider Categories", height=350)
        fig.update_traces(textinfo="percent+label", textfont_size=12)
        st.plotly_chart(fig, use_container_width=True)

    with col_b:
        fig2 = px.pie(profiles, names="preferred_shift", hole=0.5,
                      color="preferred_shift",
                      color_discrete_map={"Morning": "#74b9ff", "Lunch": "#fdcb6e",
                                          "Afternoon": "#55efc4", "Evening": "#a29bfe",
                                          "Night": "#636e72"})
        fig2.update_layout(**PLOT_LAYOUT, title="Preferred Shift Distribution", height=350)
        fig2.update_traces(textinfo="percent+label", textfont_size=12)
        st.plotly_chart(fig2, use_container_width=True)

with tab2:
    fig3 = px.scatter(
        filtered, x="attendance_consistency", y="avg_orders_per_day",
        size="total_orders", color="category",
        hover_name="rider_name",
        color_discrete_map={"Core": "#6c5ce7", "Peak": "#00b894",
                            "Flexible": "#0984e3", "Backup": "#fdcb6e",
                            "At-risk": "#e17055", "Inactive": "#636e72"},
        labels={"attendance_consistency": "Attendance Consistency %",
                "avg_orders_per_day": "Avg Orders / Day"},
    )
    fig3.update_layout(**PLOT_LAYOUT, title="Productivity vs Attendance", height=450)
    st.plotly_chart(fig3, use_container_width=True)

with tab3:
    trend_df = filtered[["rider_name", "category", "recent_trend_pct"]].sort_values("recent_trend_pct")
    colors = ["#e17055" if v < -10 else "#55efc4" if v > 10 else "#a0a4b8"
              for v in trend_df["recent_trend_pct"]]
    fig4 = go.Figure()
    fig4.add_trace(go.Bar(
        y=trend_df["rider_name"], x=trend_df["recent_trend_pct"],
        orientation="h", marker_color=colors, marker_line_width=0,
    ))
    fig4.update_layout(**PLOT_LAYOUT, title="Activity Trend (Last 14 Days vs Prior 14 Days)",
                       height=max(len(trend_df) * 28, 400),
                       xaxis_title="% Change", yaxis=dict(autorange="reversed"))
    st.plotly_chart(fig4, use_container_width=True)

# ─── Export ───────────────────────────────────────────────────────────────────
st.markdown("---")
st.download_button(
    "📥 Export Rider Profiles",
    data=profiles.to_csv(index=False),
    file_name="rider_profiles.csv",
    mime="text/csv",
)
