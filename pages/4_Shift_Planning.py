"""
Shift Planning Dashboard — Demand heatmap, staffing recommendations, deployment plan.
"""
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from data_ingestion import load_master
from rider_profiling import compute_rider_profiles
from demand_analysis import demand_heatmap_data
from deployment_engine import estimate_riders_needed, rank_riders_for_shift, generate_weekly_plan
from config import WEEKDAY_NAMES, SHIFT_ORDER
from styles import apply_custom_css, PLOT_LAYOUT

st.set_page_config(page_title="Shift Planning", page_icon="📅", layout="wide")
apply_custom_css()

st.markdown("## 📅 Shift Planning")
st.caption("Demand heatmaps, staffing estimates, rider recommendations, and weekly deployment plans")

df = load_master()
if df.empty:
    st.warning("⚠️ No data available. Please upload data first.")
    st.stop()

profiles = compute_rider_profiles(df)

# ─── Demand Heatmap ───────────────────────────────────────────────────────────
st.markdown("### 🗺️ Demand Heatmap")
st.caption("Average orders by weekday and shift — darker = higher demand")

heatmap = demand_heatmap_data(df)

fig = go.Figure(data=go.Heatmap(
    z=heatmap.values,
    x=heatmap.columns.tolist(),
    y=heatmap.index.tolist(),
    colorscale=[
        [0, "#1e2130"],
        [0.25, "#2d1b69"],
        [0.5, "#6c5ce7"],
        [0.75, "#a29bfe"],
        [1, "#dfe6e9"],
    ],
    text=heatmap.values.round(1),
    texttemplate="%{text}",
    textfont={"size": 13, "color": "white"},
    hovertemplate="Day: %{y}<br>Shift: %{x}<br>Avg Orders: %{z:.1f}<extra></extra>",
    showscale=True,
    colorbar=dict(tickfont=dict(color="#a0a4b8"),
                  title=dict(text="Avg Orders", font=dict(color="#a0a4b8"))),
))
fig.update_layout(**{**PLOT_LAYOUT, "height": 360, "xaxis_title": "Shift", "yaxis_title": "",
                     "yaxis": dict(autorange="reversed", gridcolor="#2d3148", zerolinecolor="#2d3148")})
st.plotly_chart(fig, use_container_width=True)

# ─── Staffing Estimate ────────────────────────────────────────────────────────
st.markdown("---")
st.markdown("### 🧮 Estimated Riders Needed")
st.caption("Based on historical demand and average rider productivity")

needs = estimate_riders_needed(df)
needs_pivot = needs.pivot(index="weekday", columns="shift", values="riders_needed")
needs_pivot = needs_pivot.reindex(index=WEEKDAY_NAMES, columns=SHIFT_ORDER, fill_value=0)

fig2 = go.Figure(data=go.Heatmap(
    z=needs_pivot.values,
    x=needs_pivot.columns.tolist(),
    y=needs_pivot.index.tolist(),
    colorscale=[
        [0, "#1e2130"],
        [0.5, "#00b894"],
        [1, "#e17055"],
    ],
    text=needs_pivot.values,
    texttemplate="%{text}",
    textfont={"size": 14, "color": "white"},
    hovertemplate="Day: %{y}<br>Shift: %{x}<br>Riders Needed: %{z}<extra></extra>",
    showscale=True,
    colorbar=dict(tickfont=dict(color="#a0a4b8"),
                  title=dict(text="Riders", font=dict(color="#a0a4b8"))),
))
fig2.update_layout(**{**PLOT_LAYOUT, "height": 360, "xaxis_title": "Shift", "yaxis_title": "",
                      "yaxis": dict(autorange="reversed", gridcolor="#2d3148", zerolinecolor="#2d3148")})
st.plotly_chart(fig2, use_container_width=True)

# ─── Shift Drill-Down ─────────────────────────────────────────────────────────
st.markdown("---")
st.markdown("### 🎯 Shift Drill-Down: Recommended Riders")

col_day, col_shift = st.columns(2)
with col_day:
    selected_day = st.selectbox("Select Weekday", options=WEEKDAY_NAMES, index=0)
with col_shift:
    selected_shift = st.selectbox("Select Shift", options=SHIFT_ORDER, index=1)

slot_row = needs[(needs["weekday"] == selected_day) & (needs["shift"] == selected_shift)]
n_needed = int(slot_row["riders_needed"].values[0]) if len(slot_row) > 0 else 3
avg_orders = float(slot_row["avg_orders"].values[0]) if len(slot_row) > 0 else 0

st.markdown(f"""
<div class="section-card" style="display:flex; gap:24px; flex-wrap:wrap;">
    <div style="text-align:center; flex:1;">
        <div style="color:#a0a4b8;font-size:0.8rem;">Selected Slot</div>
        <div style="font-size:1.2rem;font-weight:700;color:#a29bfe;">{selected_day} — {selected_shift}</div>
    </div>
    <div style="text-align:center; flex:1;">
        <div style="color:#a0a4b8;font-size:0.8rem;">Avg Orders</div>
        <div style="font-size:1.5rem;font-weight:700;color:#fdcb6e;">{avg_orders}</div>
    </div>
    <div style="text-align:center; flex:1;">
        <div style="color:#a0a4b8;font-size:0.8rem;">Riders Needed</div>
        <div style="font-size:1.5rem;font-weight:700;color:#55efc4;">{n_needed}</div>
    </div>
</div>
""", unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

ranked = rank_riders_for_shift(profiles, df, selected_day, selected_shift, top_n=n_needed)

if not ranked.empty:
    primary = ranked[ranked["role"] == "Primary"]
    backup = ranked[ranked["role"] == "Backup"].head(5)

    st.markdown("#### ✅ Primary Riders")
    if not primary.empty:
        st.dataframe(
            primary[["rider_name", "category", "score", "avg_orders_per_day",
                     "attendance_consistency", "completion_rate", "preferred_shift"]],
            use_container_width=True, hide_index=True,
            column_config={
                "rider_name": st.column_config.TextColumn("Rider"),
                "score": st.column_config.ProgressColumn("Fit Score", format="%.0f", min_value=0, max_value=100),
                "avg_orders_per_day": st.column_config.NumberColumn("Avg/Day", format="%.1f"),
                "attendance_consistency": st.column_config.ProgressColumn("Attendance", format="%.0f%%", min_value=0, max_value=100),
                "completion_rate": st.column_config.ProgressColumn("Completion", format="%.0f%%", min_value=0, max_value=100),
            }
        )
    else:
        st.warning("No primary riders available for this slot.")

    st.markdown("#### 🔄 Backup Riders")
    if not backup.empty:
        st.dataframe(
            backup[["rider_name", "category", "score", "avg_orders_per_day",
                    "attendance_consistency", "completion_rate", "preferred_shift"]],
            use_container_width=True, hide_index=True,
            column_config={
                "score": st.column_config.ProgressColumn("Fit Score", format="%.0f", min_value=0, max_value=100),
                "attendance_consistency": st.column_config.ProgressColumn("Attendance", format="%.0f%%", min_value=0, max_value=100),
                "completion_rate": st.column_config.ProgressColumn("Completion", format="%.0f%%", min_value=0, max_value=100),
            }
        )
    else:
        st.caption("No backup riders available.")

    if len(primary) < n_needed:
        st.error(f"⚠️ **Under-coverage warning**: Only {len(primary)} riders available but {n_needed} needed for {selected_day} {selected_shift}.")
else:
    st.info("No rider data available for ranking.")

# ─── Export Weekly Plan ───────────────────────────────────────────────────────
st.markdown("---")
st.markdown("### 📥 Export Weekly Plan")

if st.button("Generate Full Weekly Plan Export"):
    with st.spinner("Generating weekly plan..."):
        plan = generate_weekly_plan(profiles, df)
        rows = []
        for day in WEEKDAY_NAMES:
            for shift in SHIFT_ORDER:
                slot = plan[day][shift]
                rec = slot["recommended"]
                primary_names = ", ".join(rec[rec["role"] == "Primary"]["rider_name"].tolist()) if not rec.empty else "—"
                backup_names = ", ".join(rec[rec["role"] == "Backup"]["rider_name"].head(3).tolist()) if not rec.empty else "—"
                rows.append({
                    "Weekday": day,
                    "Shift": shift,
                    "Avg Orders": slot["avg_orders"],
                    "Riders Needed": slot["riders_needed"],
                    "Primary Riders": primary_names,
                    "Backup Riders": backup_names,
                })
        plan_df = pd.DataFrame(rows)

    st.dataframe(plan_df, use_container_width=True, hide_index=True, height=600)

    st.download_button(
        "📥 Download as CSV",
        data=plan_df.to_csv(index=False),
        file_name="weekly_deployment_plan.csv",
        mime="text/csv",
    )
