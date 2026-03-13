"""
Rider Profile Page — Individual rider deep-dive.
"""
import html
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from data_ingestion import load_master
from rider_profiling import compute_rider_profiles, get_rider_detail
from styles import apply_custom_css, PLOT_LAYOUT

st.set_page_config(page_title="Rider Profile", page_icon="👤", layout="wide")
apply_custom_css()

st.markdown("## 👤 Rider Profile")
st.caption("Deep-dive into individual rider behavior, preferences, and deployment fit")

df = load_master()
if df.empty:
    st.warning("⚠️ No data available. Please upload data first.")
    st.stop()

profiles = compute_rider_profiles(df)
if profiles.empty:
    st.info("No rider profiles available.")
    st.stop()

# ─── Rider Search ─────────────────────────────────────────────────────────────
rider_names = sorted([
    name for name in profiles["rider_name"].tolist()
    if str(name).strip() and str(name).strip().lower() != "nan"
])
if not rider_names:
    st.info("No valid rider names available in the dataset.")
    st.stop()

selected_rider = st.selectbox("🔍 Search / Select Rider", options=rider_names, index=0)

rider = profiles[profiles["rider_name"] == selected_rider].iloc[0]
detail = get_rider_detail(selected_rider, df)

# ─── Profile Header Card ──────────────────────────────────────────────────────
cat_class = {"Core": "core", "Peak": "peak", "Flexible": "flexible",
             "Backup": "backup", "At-risk": "atrisk", "Inactive": "inactive"}

trend_icon = {"↑ Increasing": "🟢", "↓ Declining": "🔴", "→ Stable": "🟡"}
safe_name = html.escape(str(rider["rider_name"]))
safe_category = html.escape(str(rider["category"]))
safe_trend = html.escape(str(rider["recent_trend"]))
safe_preferred_shift = html.escape(str(rider["preferred_shift"]))
safe_preferred_weekday = html.escape(str(rider["preferred_weekday"]))
avatar_letter = html.escape(selected_rider[:1].upper()) if selected_rider else "?"

st.markdown(f"""
<div class="section-card" style="display:flex; gap:32px; align-items:center; flex-wrap:wrap;">
    <div style="flex:0 0 auto; text-align:center;">
        <div style="width:80px;height:80px;border-radius:50%;
                    background:linear-gradient(135deg, #6c5ce7, #a29bfe);
                    display:flex;align-items:center;justify-content:center;
                    font-size:2rem;color:white;font-weight:700;margin:0 auto;">
            {avatar_letter}
        </div>
        <div style="margin-top:8px;">
            <span class="badge badge-{cat_class.get(rider['category'], 'core')}">{safe_category}</span>
        </div>
    </div>
    <div style="flex:1; min-width:250px;">
        <h2 style="margin:0 0 8px 0;">{safe_name}</h2>
        <div style="display:grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap:12px;">
            <div><span style="color:#a0a4b8;font-size:0.8rem;">Total Orders</span><br><strong style="font-size:1.3rem;color:#a29bfe;">{rider['total_orders']}</strong></div>
            <div><span style="color:#a0a4b8;font-size:0.8rem;">Delivered</span><br><strong style="font-size:1.3rem;color:#55efc4;">{rider['delivered_orders']}</strong></div>
            <div><span style="color:#a0a4b8;font-size:0.8rem;">Completion Rate</span><br><strong style="font-size:1.3rem;color:#fdcb6e;">{rider['completion_rate']}%</strong></div>
            <div><span style="color:#a0a4b8;font-size:0.8rem;">Active Days</span><br><strong style="font-size:1.3rem;color:#74b9ff;">{rider['active_days']}</strong></div>
            <div><span style="color:#a0a4b8;font-size:0.8rem;">Avg Orders/Day</span><br><strong style="font-size:1.3rem;color:#a29bfe;">{rider['avg_orders_per_day']}</strong></div>
            <div><span style="color:#a0a4b8;font-size:0.8rem;">Trend</span><br><strong style="font-size:1.3rem;">{trend_icon.get(rider['recent_trend'], '⚪')} {safe_trend}</strong></div>
        </div>
    </div>
</div>
""", unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# ─── Detail Charts ────────────────────────────────────────────────────────────
tab1, tab2, tab3 = st.tabs(["📅 Activity Pattern", "⏰ Time Preferences", "📊 Performance"])

with tab1:
    if detail.get("daily_orders") is not None and not detail["daily_orders"].empty:
        col_l, col_r = st.columns(2)

        with col_l:
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=detail["daily_orders"]["date"],
                y=detail["daily_orders"]["orders"],
                mode="lines+markers",
                line=dict(color="#a29bfe", width=2.5),
                marker=dict(size=6),
                fill="tozeroy", fillcolor="rgba(162, 155, 254, 0.1)"
            ))
            fig.update_layout(**PLOT_LAYOUT, title="Daily Order Volume", height=320)
            st.plotly_chart(fig, use_container_width=True)

        with col_r:
            wk = detail["weekday_orders"]
            max_day = wk.loc[wk["orders"].idxmax(), "weekday"]
            colors = ["#6c5ce7" if d == max_day else "#a29bfe" for d in wk["weekday"]]
            fig2 = go.Figure()
            fig2.add_trace(go.Bar(
                x=wk["weekday"], y=wk["orders"],
                marker_color=colors, marker_line_width=0
            ))
            fig2.update_layout(**PLOT_LAYOUT, title="Orders by Weekday", height=320)
            st.plotly_chart(fig2, use_container_width=True)

with tab2:
    if detail:
        col_a, col_b = st.columns(2)

        with col_a:
            hr = detail["hourly_distribution"]
            fig3 = go.Figure()
            fig3.add_trace(go.Bar(
                x=hr["hour"], y=hr["orders"],
                marker_color="#74b9ff", marker_line_width=0,
                opacity=0.85
            ))
            fig3.update_layout(**PLOT_LAYOUT, title="Orders by Hour",
                              height=320, xaxis_title="Hour (0-23)")
            st.plotly_chart(fig3, use_container_width=True)

        with col_b:
            sh = detail["shift_orders"]
            shift_colors = {"Morning": "#74b9ff", "Lunch": "#fdcb6e", "Afternoon": "#55efc4",
                           "Evening": "#a29bfe", "Night": "#636e72"}
            fig4 = go.Figure()
            fig4.add_trace(go.Bar(
                x=sh["shift"], y=sh["orders"],
                marker_color=[shift_colors.get(s, "#a29bfe") for s in sh["shift"]],
                marker_line_width=0
            ))
            fig4.update_layout(**PLOT_LAYOUT, title="Orders by Shift", height=320)
            st.plotly_chart(fig4, use_container_width=True)

        st.markdown(f"""
        <div class="section-card">
            <h3>⏱️ Working Hours Summary</h3>
            <div style="display:grid; grid-template-columns: repeat(4, 1fr); gap:16px; text-align:center;">
                <div>
                    <div style="color:#a0a4b8;font-size:0.8rem;">Avg Start Time</div>
                    <div style="font-size:1.3rem;font-weight:700;color:#55efc4;">{int(rider['avg_first_hour'])}:00</div>
                </div>
                <div>
                    <div style="color:#a0a4b8;font-size:0.8rem;">Avg End Time</div>
                    <div style="font-size:1.3rem;font-weight:700;color:#e17055;">{int(rider['avg_last_hour'])}:00</div>
                </div>
                <div>
                    <div style="color:#a0a4b8;font-size:0.8rem;">Preferred Shift</div>
                    <div style="font-size:1.3rem;font-weight:700;color:#a29bfe;">{safe_preferred_shift}</div>
                </div>
                <div>
                    <div style="color:#a0a4b8;font-size:0.8rem;">Preferred Day</div>
                    <div style="font-size:1.3rem;font-weight:700;color:#fdcb6e;">{safe_preferred_weekday}</div>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

with tab3:
    if detail:
        col_x, col_y = st.columns(2)

        with col_x:
            status = detail["status_distribution"]
            color_map = {"Delivered": "#55efc4", "Cancelled": "#e17055", "Returned": "#fdcb6e"}
            fig5 = px.pie(status, names="status", values="count", hole=0.5,
                         color="status", color_discrete_map=color_map)
            fig5.update_layout(**PLOT_LAYOUT, title="Order Status Breakdown", height=320)
            fig5.update_traces(textinfo="percent+label", textfont_size=12)
            st.plotly_chart(fig5, use_container_width=True)

        with col_y:
            fig6 = go.Figure(go.Indicator(
                mode="gauge+number+delta",
                value=rider["attendance_consistency"],
                title={"text": "Attendance Consistency", "font": {"size": 16, "color": "#a0a4b8"}},
                number={"suffix": "%", "font": {"size": 36, "color": "#a29bfe"}},
                gauge={
                    "axis": {"range": [0, 100], "tickfont": {"color": "#a0a4b8"}},
                    "bar": {"color": "#6c5ce7"},
                    "bgcolor": "#1e2130",
                    "borderwidth": 0,
                    "steps": [
                        {"range": [0, 40], "color": "rgba(225, 112, 85, 0.2)"},
                        {"range": [40, 70], "color": "rgba(253, 203, 110, 0.2)"},
                        {"range": [70, 100], "color": "rgba(85, 239, 196, 0.2)"},
                    ],
                    "threshold": {
                        "line": {"color": "#55efc4", "width": 3},
                        "thickness": 0.8,
                        "value": rider["attendance_consistency"],
                    },
                },
            ))
            fig6.update_layout(**PLOT_LAYOUT, height=320)
            st.plotly_chart(fig6, use_container_width=True)

# ─── Deployment Recommendation ────────────────────────────────────────────────
st.markdown("---")
st.markdown("### 🚀 Deployment Recommendation")

dep_text = ""
if rider["category"] == "Core":
    dep_text = f"**{rider['rider_name']}** is a **Core rider** — highly reliable, consistent attendance, and strong output. Recommended for daily scheduling in the **{rider['preferred_shift']}** shift, especially on **{rider['preferred_weekday']}**."
elif rider["category"] == "Peak":
    dep_text = f"**{rider['rider_name']}** is a **Peak rider** — excels during high-demand shifts. Best deployed during **{rider['preferred_shift']}** on peak days."
elif rider["category"] == "At-risk":
    dep_text = f"⚠️ **{rider['rider_name']}** is **At-risk** — activity declining or low completion rate. Consider a check-in before scheduling."
elif rider["category"] == "Inactive":
    dep_text = f"🔴 **{rider['rider_name']}** is **Inactive** — no activity in the last 14 days. May need reactivation or removal from rosters."
elif rider["category"] == "Backup":
    dep_text = f"**{rider['rider_name']}** is a **Backup rider** — low frequency but reliable when active. Good as overflow support during **{rider['preferred_shift']}**."
else:
    dep_text = f"**{rider['rider_name']}** is a **Flexible rider** — can be deployed across shifts. Moderate consistency makes them suitable for variable scheduling."

st.info(dep_text)
