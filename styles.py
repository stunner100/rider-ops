"""
Shared styles and helpers for the Streamlit dashboard.
"""
import streamlit as st


def apply_custom_css():
    """Inject the premium dark‐theme CSS into the page."""
    st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');

:root {
    --bg-primary: #0f1117;
    --bg-secondary: #1a1d29;
    --bg-card: #1e2130;
    --bg-card-hover: #252840;
    --accent-primary: #6c5ce7;
    --accent-secondary: #a29bfe;
    --accent-success: #00b894;
    --accent-warning: #fdcb6e;
    --accent-danger: #e17055;
    --text-primary: #f8f9fa;
    --text-secondary: #a0a4b8;
    --border-color: #2d3148;
    --gradient-1: linear-gradient(135deg, #6c5ce7 0%, #a29bfe 100%);
    --gradient-2: linear-gradient(135deg, #00b894 0%, #55efc4 100%);
    --gradient-3: linear-gradient(135deg, #e17055 0%, #fdcb6e 100%);
    --gradient-4: linear-gradient(135deg, #0984e3 0%, #74b9ff 100%);
    --shadow-card: 0 4px 24px rgba(0, 0, 0, 0.3);
    --shadow-glow: 0 0 30px rgba(108, 92, 231, 0.15);
}

html, body, [class*="css"] {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif !important;
}

.stApp { background: var(--bg-primary) !important; }

section[data-testid="stSidebar"] {
    background: var(--bg-secondary) !important;
    border-right: 1px solid var(--border-color) !important;
}

h1, h2, h3, h4, h5, h6 {
    color: var(--text-primary) !important;
    font-weight: 700 !important;
    letter-spacing: -0.02em !important;
}
h1 { font-size: 2rem !important; }
h2 { font-size: 1.5rem !important; }
h3 { font-size: 1.2rem !important; }

/* Scope white text to main content and sidebar only — NOT into widget internals */
.stApp > header,
.stApp .stMarkdown p,
.stApp .stMarkdown li,
.stApp .stMarkdown span,
.stApp .stMarkdown div,
.stApp .stCaption,
section[data-testid="stSidebar"] .stMarkdown p,
section[data-testid="stSidebar"] .stMarkdown span,
section[data-testid="stSidebar"] .stMarkdown div {
    color: var(--text-primary) !important;
}

/* Sidebar navigation links (Streamlit multi-page nav) */
section[data-testid="stSidebar"] a,
section[data-testid="stSidebar"] a span,
section[data-testid="stSidebar"] [data-testid="stSidebarNav"] span,
section[data-testid="stSidebar"] [data-testid="stSidebarNav"] li,
section[data-testid="stSidebar"] [data-testid="stSidebarNav"] p {
    color: var(--text-secondary) !important;
    transition: color 0.2s ease;
}
section[data-testid="stSidebar"] a:hover span,
section[data-testid="stSidebar"] a:hover {
    color: var(--accent-secondary) !important;
}
section[data-testid="stSidebar"] [aria-selected="true"] span {
    color: var(--text-primary) !important;
    font-weight: 600 !important;
}

/* Labels for widgets (selectbox, slider, radio, etc.) */
.stSelectbox label,
.stMultiSelect label,
.stRadio label,
.stTextInput label,
.stTextArea label,
.stFileUploader label,
.stSlider label {
    color: var(--text-primary) !important;
}

.kpi-card {
    background: var(--bg-card);
    border: 1px solid var(--border-color);
    border-radius: 16px;
    padding: 24px;
    text-align: center;
    box-shadow: var(--shadow-card);
    transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
    position: relative;
    overflow: hidden;
    animation: fadeInUp 0.5s ease forwards;
}
.kpi-card::before {
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 3px;
    border-radius: 16px 16px 0 0;
}
.kpi-card:hover {
    transform: translateY(-4px);
    box-shadow: var(--shadow-glow);
    border-color: var(--accent-primary);
}
.kpi-card.purple::before { background: var(--gradient-1); }
.kpi-card.green::before { background: var(--gradient-2); }
.kpi-card.orange::before { background: var(--gradient-3); }
.kpi-card.blue::before { background: var(--gradient-4); }

.kpi-value {
    font-size: 2.2rem;
    font-weight: 800;
    letter-spacing: -0.03em;
    margin: 8px 0 4px 0;
}
.kpi-value.purple { color: #a29bfe; }
.kpi-value.green { color: #55efc4; }
.kpi-value.orange { color: #fdcb6e; }
.kpi-value.blue { color: #74b9ff; }

.kpi-label {
    font-size: 0.85rem;
    color: var(--text-secondary) !important;
    font-weight: 500;
    text-transform: uppercase;
    letter-spacing: 0.05em;
}
.kpi-sublabel {
    font-size: 0.75rem;
    color: var(--text-secondary) !important;
    margin-top: 4px;
    font-weight: 400;
}

.badge {
    display: inline-block;
    padding: 4px 12px;
    border-radius: 20px;
    font-size: 0.75rem;
    font-weight: 600;
    letter-spacing: 0.03em;
}
.badge-core { background: rgba(108,92,231,0.2); color: #a29bfe !important; border: 1px solid rgba(108,92,231,0.3); }
.badge-peak { background: rgba(0,184,148,0.2); color: #55efc4 !important; border: 1px solid rgba(0,184,148,0.3); }
.badge-flexible { background: rgba(9,132,227,0.2); color: #74b9ff !important; border: 1px solid rgba(9,132,227,0.3); }
.badge-backup { background: rgba(253,203,110,0.2); color: #fdcb6e !important; border: 1px solid rgba(253,203,110,0.3); }
.badge-atrisk { background: rgba(225,112,85,0.2); color: #e17055 !important; border: 1px solid rgba(225,112,85,0.3); }
.badge-inactive { background: rgba(99,110,114,0.2); color: #b2bec3 !important; border: 1px solid rgba(99,110,114,0.3); }

/* ─── Dark-themed Dataframes & Tables ─────────────────────────────────────── */
.stDataFrame { border-radius: 12px !important; overflow: hidden !important; }

/* Glide Data Grid (Streamlit's st.dataframe component) */
[data-testid="stDataFrame"] > div {
    background: var(--bg-card) !important;
    border: 1px solid var(--border-color) !important;
    border-radius: 12px !important;
}

/* st.metric dark styling */
[data-testid="stMetric"] {
    background: var(--bg-card);
    border: 1px solid var(--border-color);
    border-radius: 12px;
    padding: 12px 16px;
}
[data-testid="stMetric"] label { color: var(--text-secondary) !important; }
[data-testid="stMetric"] [data-testid="stMetricValue"] { color: var(--text-primary) !important; }

/* Alert/info/warning/error/success boxes — explicit readable text */
[data-testid="stAlert"] p,
[data-testid="stAlert"] span,
[data-testid="stAlert"] div,
[data-testid="stAlert"] li,
.stAlert p, .stAlert span, .stAlert div {
    color: #e8e8e8 !important;
    font-weight: 500 !important;
}
/* Success alerts */
[data-testid="stAlert"][data-baseweb*="positive"] p,
div[data-testid="stNotification"][kind="success"] p,
div.stSuccess p {
    color: #d4edda !important;
}
/* Warning alerts */
div[data-testid="stNotification"][kind="warning"] p,
div.stWarning p {
    color: #fff3cd !important;
}
/* Error alerts */
div[data-testid="stNotification"][kind="error"] p,
div.stError p {
    color: #f8d7da !important;
}

/* Inline code tags — bright readable text */
code {
    color: #e2e8f0 !important;
    background: rgba(45, 49, 72, 0.8) !important;
    padding: 2px 6px;
    border-radius: 4px;
    font-size: 0.85em;
}

/* Section-card inner text should also be bright */
.section-card p, .section-card span, .section-card div, .section-card code {
    color: var(--text-primary) !important;
}

.stTabs [data-baseweb="tab-list"] { gap: 8px; background: transparent; }
.stTabs [data-baseweb="tab"] {
    background: var(--bg-card) !important;
    border-radius: 10px !important;
    color: var(--text-secondary) !important;
    border: 1px solid var(--border-color) !important;
    padding: 8px 20px !important;
    font-weight: 500 !important;
}
.stTabs [aria-selected="true"] {
    background: var(--accent-primary) !important;
    color: white !important;
    border-color: var(--accent-primary) !important;
}

[data-testid="stFileUploader"] {
    background: var(--bg-card) !important;
    border: 2px dashed var(--border-color) !important;
    border-radius: 16px !important;
    padding: 32px !important;
}

.stSelectbox > div > div,
.stTextInput > div > div > input,
.stTextArea > div > div > textarea {
    background: var(--bg-card) !important;
    border: 1px solid var(--border-color) !important;
    border-radius: 10px !important;
    color: var(--text-primary) !important;
}

.stButton > button {
    background: var(--gradient-1) !important;
    color: white !important;
    border: none !important;
    border-radius: 10px !important;
    font-weight: 600 !important;
    padding: 8px 24px !important;
    transition: all 0.3s ease !important;
}
.stButton > button:hover {
    transform: translateY(-2px) !important;
    box-shadow: 0 8px 25px rgba(108,92,231,0.4) !important;
}

hr { border-color: var(--border-color) !important; margin: 24px 0 !important; }

::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: var(--bg-secondary); }
::-webkit-scrollbar-thumb { background: var(--border-color); border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: var(--accent-primary); }

.section-card {
    background: var(--bg-card);
    border: 1px solid var(--border-color);
    border-radius: 16px;
    padding: 24px;
    margin-bottom: 16px;
    box-shadow: var(--shadow-card);
}

@keyframes fadeInUp {
    from { opacity: 0; transform: translateY(20px); }
    to { opacity: 1; transform: translateY(0); }
}
</style>
""", unsafe_allow_html=True)


# Standard Plotly layout for dark theme
PLOT_LAYOUT = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(family="Inter", color="#a0a4b8"),
    margin=dict(l=40, r=20, t=40, b=40),
    xaxis=dict(gridcolor="#2d3148", zerolinecolor="#2d3148"),
    yaxis=dict(gridcolor="#2d3148", zerolinecolor="#2d3148"),
)
