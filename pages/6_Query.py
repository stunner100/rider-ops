"""
Query Page — Natural language operational queries.
"""
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from data_ingestion import load_master
from query_engine import query
from styles import apply_custom_css, PLOT_LAYOUT

st.set_page_config(page_title="Ask a Question", page_icon="💬", layout="wide")
apply_custom_css()

st.markdown("## 💬 Ask a Question")
st.caption("Query your rider data in plain English — get instant answers with charts and tables")

df = load_master()
if df.empty:
    st.warning("⚠️ No data available. Please upload data first.")
    st.stop()

# ─── Example Questions ────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### 💡 Example Questions")
    examples = [
        "Who are my top 10 riders by attendance?",
        "Which riders work most in the evening?",
        "Which riders have reduced activity?",
        "How many riders do I need for Friday lunch?",
        "Which riders work at least 4 days and average above 10 orders?",
        "Who are my core riders?",
        "Show me inactive riders",
        "What are the busiest demand periods?",
        "Who are the top riders by productivity?",
    ]
    for ex in examples:
        if st.button(ex, key=f"ex_{ex[:30]}", use_container_width=True):
            st.session_state["query_input"] = ex

# ─── Query Input ──────────────────────────────────────────────────────────────
default_val = st.session_state.get("query_input", "")

question = st.text_input(
    "🔍 Type your question here",
    value=default_val,
    placeholder="e.g. Who are my top riders by attendance this month?",
    key="query_box"
)

if question:
    with st.spinner("Thinking..."):
        result = query(question, df)

    st.markdown("---")
    st.markdown("### 💬 Answer")
    st.markdown(result["answer"])
    if result["filters"]:
        st.caption(f"📋 {result['filters']}")

    if result["table"] is not None and not result["table"].empty:
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("### 📊 Supporting Data")
        st.dataframe(result["table"], use_container_width=True, hide_index=True,
                     height=min(len(result["table"]) * 40 + 40, 500))

        if result["chart_type"] == "bar" and len(result["table"]) > 0:
            table = result["table"]
            text_cols = table.select_dtypes(include=["object"]).columns.tolist()
            num_cols = table.select_dtypes(include=["number"]).columns.tolist()

            if text_cols and num_cols:
                x_col = text_cols[0]
                y_col = num_cols[0]

                fig = go.Figure()
                fig.add_trace(go.Bar(
                    x=table[x_col], y=table[y_col],
                    marker_color="#a29bfe", marker_line_width=0,
                    opacity=0.85,
                ))
                fig.update_layout(**PLOT_LAYOUT,
                                  title=f"{y_col.replace('_', ' ').title()} by {x_col.replace('_', ' ').title()}",
                                  height=350)
                st.plotly_chart(fig, use_container_width=True)

        st.download_button(
            "📥 Download Results",
            data=result["table"].to_csv(index=False),
            file_name="query_results.csv",
            mime="text/csv",
        )

    if "query_input" in st.session_state:
        del st.session_state["query_input"]
