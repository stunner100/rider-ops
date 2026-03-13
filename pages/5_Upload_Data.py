"""
Upload Data & Data Health Page — File upload, validation, upload history.
"""
import html
import streamlit as st
import pandas as pd
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from data_ingestion import (
    validate_csv, clean_data, append_to_master,
    log_upload, load_upload_log, load_master,
    map_columns,
)
from config import REQUIRED_COLUMNS, OPTIONAL_COLUMNS, COLUMN_ALIASES
from styles import apply_custom_css

st.set_page_config(page_title="Upload Data", page_icon="📤", layout="wide")
apply_custom_css()

st.markdown("## 📤 Upload Data")
st.caption("Import new rider order files, validate data quality, and grow your historical dataset")

# ─── Upload Section ───────────────────────────────────────────────────────────
st.markdown("### 📁 Upload New File")

# Show accepted aliases for each required column
alias_html_items = []
for internal, aliases in COLUMN_ALIASES.items():
    if internal in REQUIRED_COLUMNS:
        tag = "badge-core"
        label = "required"
    else:
        tag = "badge-flexible"
        label = "optional"
    alias_str = " · ".join(f"<code>{a}</code>" for a in aliases)
    alias_html_items.append(
        f'<div style="margin-bottom:8px;">'
        f'<span class="badge {tag}" style="margin-right:8px;">{internal}</span>'
        f'<span style="color:#a0a4b8;font-size:0.8rem;">accepts: {alias_str}</span>'
        f'</div>'
    )

st.markdown(f"""
<div class="section-card">
    <h4>Accepted Columns & Aliases</h4>
    <div style="margin-top:8px;">{"".join(alias_html_items)}</div>
</div>
""", unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

uploaded_file = st.file_uploader(
    "Drop your CSV or Excel file here",
    type=["csv", "xlsx", "xls"],
    help="Upload a file with rider order data. Columns will be auto-mapped to internal names."
)

if uploaded_file is not None:
    try:
        if uploaded_file.name.endswith((".xlsx", ".xls")):
            raw_df = pd.read_excel(uploaded_file)
        else:
            raw_df = pd.read_csv(uploaded_file)
    except Exception as e:
        st.error(f"❌ Failed to read file: {str(e)}")
        st.stop()

    st.markdown(f"**File:** `{uploaded_file.name}` — **{len(raw_df):,} rows** × {len(raw_df.columns)} columns")

    with st.expander("👀 Preview Raw Data", expanded=False):
        st.dataframe(raw_df.head(20), use_container_width=True, hide_index=True)

    # ── Column Mapping ──────────────────────────────────────────────────────
    mapping_result = map_columns(raw_df)  # renames df in place

    if mapping_result["mapped"]:
        mapped_items = "".join(
            f'<div style="padding:4px 0;">'
            f'<code style="color:#fdcb6e;">{html.escape(str(orig))}</code>'
            f' <span style="color:#a0a4b8;">→</span> '
            f'<code style="color:#55efc4;">{html.escape(str(internal))}</code>'
            f'</div>'
            for orig, internal in mapping_result["mapped"].items()
        )
        st.markdown(f"""
        <div class="section-card" style="border-color: rgba(0,184,148,0.4);">
            <h4>✅ Column Mapping Applied</h4>
            <div style="margin-top:8px;">{mapped_items}</div>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.info("ℹ️ No column remapping needed — headers already match internal names.")

    if mapping_result["unmapped_required"]:
        missing_names = mapping_result["unmapped_required"]
        hints = []
        for m in missing_names:
            accepted = ", ".join(f"`{a}`" for a in COLUMN_ALIASES.get(m, [m]))
            hints.append(f"- **{m}**: expected one of {accepted}")
        st.error(
            f"❌ Could not map required column(s): **{', '.join(missing_names)}**\n\n"
            + "\n".join(hints)
            + "\n\nPlease rename the column(s) in your file or add an alias in the config."
        )
        st.stop()

    # ── Validation (runs on the already-mapped DataFrame) ───────────────────
    validation = validate_csv(raw_df)

    if not validation["valid"]:
        st.error("❌ Validation Failed:")
        for err in validation["errors"]:
            st.markdown(f"- {err}")
        st.stop()

    if validation["warnings"]:
        for warn in validation["warnings"]:
            st.warning(f"⚠️ {warn}")

    st.success("✅ Validation passed!")

    if st.button("🚀 Process & Upload", type="primary"):
        with st.spinner("Cleaning, deduplicating, and appending data..."):
            clean_result = clean_data(raw_df, return_stats=True)
            cleaned = clean_result["clean_df"]
            stats = append_to_master(cleaned, original_count=clean_result["original_count"])
            stats["cleaned_count"] = clean_result["cleaned_count"]
            stats["rows_dropped_during_cleaning"] = clean_result["rows_dropped_during_cleaning"]
            stats["errors"] = validation.get("errors", [])
            log_upload(uploaded_file.name, stats)

        st.markdown("---")
        st.markdown("### 📊 Upload Results")

        r1, r2, r3, r4, r5, r6 = st.columns(6)
        r1.markdown(f"""
        <div class="kpi-card purple" style="padding:16px;">
            <div class="kpi-label">Rows in File</div>
            <div class="kpi-value purple">{stats['original_count']:,}</div>
        </div>""", unsafe_allow_html=True)

        r2.markdown(f"""
        <div class="kpi-card green" style="padding:16px;">
            <div class="kpi-label">Rows After Cleaning</div>
            <div class="kpi-value green">{stats['cleaned_count']:,}</div>
        </div>""", unsafe_allow_html=True)

        r3.markdown(f"""
        <div class="kpi-card orange" style="padding:16px;">
            <div class="kpi-label">Dropped in Cleaning</div>
            <div class="kpi-value orange">{stats['rows_dropped_during_cleaning']:,}</div>
        </div>""", unsafe_allow_html=True)

        r4.markdown(f"""
        <div class="kpi-card green" style="padding:16px;">
            <div class="kpi-label">Rows Added</div>
            <div class="kpi-value green">{stats['rows_added']:,}</div>
        </div>""", unsafe_allow_html=True)

        r5.markdown(f"""
        <div class="kpi-card orange" style="padding:16px;">
            <div class="kpi-label">Duplicates Removed</div>
            <div class="kpi-value orange">{stats['duplicates_removed']:,}</div>
        </div>""", unsafe_allow_html=True)

        r6.markdown(f"""
        <div class="kpi-card blue" style="padding:16px;">
            <div class="kpi-label">Total Master Rows</div>
            <div class="kpi-value blue">{stats['total_rows']:,}</div>
        </div>""", unsafe_allow_html=True)

        if stats["rows_dropped_during_cleaning"] > 0:
            st.warning(
                f"⚠️ {stats['rows_dropped_during_cleaning']:,} row(s) were dropped during cleaning because "
                "required fields were blank or dates could not be parsed."
            )

        if stats["rows_added"] == 0:
            st.info("ℹ️ No new rows added — all records already exist in the master dataset.")
        else:
            st.success(f"🎉 Successfully added **{stats['rows_added']:,}** new orders to the master dataset!")
            st.balloons()

# ─── Data Health ──────────────────────────────────────────────────────────────
st.markdown("---")
st.markdown("### 🏥 Data Health")

master_df = load_master()

if master_df.empty:
    st.info("No data in the master dataset yet. Upload a file above to get started.")
else:
    h1, h2, h3, h4 = st.columns(4)

    h1.metric("Total Records", f"{len(master_df):,}")
    h2.metric("Unique Riders", master_df["rider_name"].nunique())
    h3.metric("Date Range", f"{master_df['order_datetime'].min().date()} → {master_df['order_datetime'].max().date()}")
    h4.metric("Unique Dates", master_df["order_datetime"].dt.date.nunique())

    st.markdown("#### Missing Values")
    missing = master_df.isnull().sum()
    missing = missing[missing > 0]
    if missing.empty:
        st.success("✅ No missing values in any column!")
    else:
        missing_df = pd.DataFrame({"Column": missing.index, "Missing Count": missing.values,
                                    "% Missing": (missing.values / len(master_df) * 100).round(1)})
        st.dataframe(missing_df, use_container_width=True, hide_index=True)

# ─── Upload History ───────────────────────────────────────────────────────────
st.markdown("---")
st.markdown("### 📜 Upload History")

log_df = load_upload_log()
if log_df.empty:
    st.caption("No uploads recorded yet.")
else:
    st.dataframe(
        log_df.sort_values("timestamp", ascending=False),
        use_container_width=True,
        hide_index=True,
        column_config={
            "timestamp": st.column_config.TextColumn("Timestamp"),
            "filename": st.column_config.TextColumn("Filename"),
            "rows_in_file": st.column_config.NumberColumn("Rows in File"),
            "rows_after_cleaning": st.column_config.NumberColumn("Rows After Cleaning"),
            "rows_dropped_during_cleaning": st.column_config.NumberColumn("Dropped in Cleaning"),
            "rows_added": st.column_config.NumberColumn("Rows Added"),
            "duplicates_removed": st.column_config.NumberColumn("Duplicates"),
            "total_master_rows": st.column_config.NumberColumn("Total Master"),
        }
    )
