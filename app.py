"""
Rider Operations Intelligence Dashboard — Main App Entry Point
"""
import streamlit as st
import os, sys

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from data_ingestion import load_master

# ─── Page Config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Rider Ops Intelligence",
    page_icon="🏍️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── Apply Custom CSS ─────────────────────────────────────────────────────────
from styles import apply_custom_css
apply_custom_css()


# ─── Sidebar ──────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("""
    <div style="text-align:center; padding: 16px 0 8px 0;">
        <div style="font-size: 2.5rem;">🏍️</div>
        <h2 style="margin:8px 0 2px 0; font-size:1.3rem;">Rider Ops</h2>
        <p style="color: #a0a4b8 !important; font-size:0.8rem; margin:0;">Intelligence Dashboard</p>
    </div>
    """, unsafe_allow_html=True)
    st.markdown("---")

    # Data status
    master_df = load_master()
    if master_df.empty:
        st.warning("⚠️ No data loaded. Upload data via **Upload Data** page.")
    else:
        st.success(f"✅ {len(master_df):,} orders loaded")
        st.caption(f"Riders: {master_df['rider_name'].nunique()} · Days: {master_df['order_datetime'].dt.date.nunique()}")

    st.markdown("---")
    st.markdown("""
    <div style="padding: 8px 0; font-size: 0.75rem; color: #a0a4b8 !important;">
        <strong>Pages</strong><br><br>
        📊 Executive Dashboard<br>
        🏆 Rider Performance<br>
        👤 Rider Profile<br>
        📅 Shift Planning<br>
        📤 Upload Data<br>
        💬 Ask a Question
    </div>
    """, unsafe_allow_html=True)


# ─── Main Landing ────────────────────────────────────────────────────────────
st.markdown("""
<div style="text-align:center; padding: 60px 0 40px 0;">
    <h1 style="font-size: 2.8rem !important; font-weight: 800 !important;
               background: linear-gradient(135deg, #6c5ce7, #a29bfe, #74b9ff);
               -webkit-background-clip: text; -webkit-text-fill-color: transparent;
               margin-bottom: 12px;">
        Rider Operations Intelligence
    </h1>
    <p style="color: #a0a4b8 !important; font-size: 1.1rem; max-width: 600px; margin: 0 auto;">
        Transform rider order exports into actionable staffing intelligence.
        Upload data, analyze patterns, and plan deployments — all in one place.
    </p>
</div>
""", unsafe_allow_html=True)

# Quick access cards
col1, col2, col3 = st.columns(3)

with col1:
    st.markdown("""
    <div class="kpi-card purple" style="cursor:pointer;">
        <div style="font-size: 2rem; margin-bottom: 8px;">📊</div>
        <h3 style="font-size: 1.1rem !important; margin-bottom: 8px;">Executive Dashboard</h3>
        <p style="color: #a0a4b8 !important; font-size: 0.85rem;">
            KPIs, order trends, peak windows, and delivery performance at a glance.
        </p>
    </div>
    """, unsafe_allow_html=True)

with col2:
    st.markdown("""
    <div class="kpi-card green" style="cursor:pointer;">
        <div style="font-size: 2rem; margin-bottom: 8px;">🏆</div>
        <h3 style="font-size: 1.1rem !important; margin-bottom: 8px;">Rider Performance</h3>
        <p style="color: #a0a4b8 !important; font-size: 0.85rem;">
            Leaderboards, rider categories, attendance metrics, and productivity rankings.
        </p>
    </div>
    """, unsafe_allow_html=True)

with col3:
    st.markdown("""
    <div class="kpi-card blue" style="cursor:pointer;">
        <div style="font-size: 2rem; margin-bottom: 8px;">📅</div>
        <h3 style="font-size: 1.1rem !important; margin-bottom: 8px;">Shift Planning</h3>
        <p style="color: #a0a4b8 !important; font-size: 0.85rem;">
            Demand heatmaps, staffing recommendations, and weekly deployment plans.
        </p>
    </div>
    """, unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

col4, col5, col6 = st.columns(3)

with col4:
    st.markdown("""
    <div class="kpi-card orange" style="cursor:pointer;">
        <div style="font-size: 2rem; margin-bottom: 8px;">👤</div>
        <h3 style="font-size: 1.1rem !important; margin-bottom: 8px;">Rider Profiles</h3>
        <p style="color: #a0a4b8 !important; font-size: 0.85rem;">
            Deep-dive into individual rider behavior, preferences, and deployment fit.
        </p>
    </div>
    """, unsafe_allow_html=True)

with col5:
    st.markdown("""
    <div class="kpi-card purple" style="cursor:pointer;">
        <div style="font-size: 2rem; margin-bottom: 8px;">📤</div>
        <h3 style="font-size: 1.1rem !important; margin-bottom: 8px;">Upload Data</h3>
        <p style="color: #a0a4b8 !important; font-size: 0.85rem;">
            Import new CSV files, validate data quality, and grow your historical dataset.
        </p>
    </div>
    """, unsafe_allow_html=True)

with col6:
    st.markdown("""
    <div class="kpi-card green" style="cursor:pointer;">
        <div style="font-size: 2rem; margin-bottom: 8px;">💬</div>
        <h3 style="font-size: 1.1rem !important; margin-bottom: 8px;">Ask a Question</h3>
        <p style="color: #a0a4b8 !important; font-size: 0.85rem;">
            Query your data in plain English. Get instant answers with charts and tables.
        </p>
    </div>
    """, unsafe_allow_html=True)

st.markdown("""
<div style="text-align:center; padding: 40px 0 20px 0; color: #636e72 !important; font-size: 0.8rem;">
    Use the sidebar ← to navigate between pages
</div>
""", unsafe_allow_html=True)
