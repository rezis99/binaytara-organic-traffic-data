"""
Binaytara SEO Monitor v3.1 — Tab: Keyword Deep Dive
Per-page GSC query analysis with New/Lost/Retained detection.
"""
import streamlit as st
import pandas as pd
import plotly.express as px
from config import SITE_DOMAIN, BRAND_NAVY, BRAND_GREEN, BRAND_RED
from export import to_excel_bytes, make_filename


def render(dates, organic_only, section_filter):
    from data.gsc import compare_queries, fetch_gsc_page_summary

    cs, ce = dates["curr_start"], dates["curr_end"]
    ps, pe = dates["prev_start"], dates["prev_end"]

    with st.spinner("Loading page list..."):
        gsc_summary = fetch_gsc_page_summary(cs, ce)

    if gsc_summary.empty:
        st.warning("No GSC data for this range.")
        return

    page_list = gsc_summary.sort_values("gsc_clicks", ascending=False)["page"].tolist()
    selected_page = st.selectbox("Select a page to investigate", page_list, index=0,
                                  format_func=lambda x: x.replace(SITE_DOMAIN, ""))
    if not selected_page:
        st.info("Select a page above.")
        return

    with st.spinner(f"Fetching keyword data..."):
        qdf = compare_queries(selected_page, cs, ce, ps, pe)

    if qdf.empty:
        st.warning("No query data for this page in either period.")
        return

    # Column names from compare_queries: clicks_curr, clicks_prev, clicks_change,
    # impr_curr, impr_prev, impr_change, pos_curr, pos_prev, pos_change, status, query
    total_curr = int(qdf["clicks_curr"].sum())
    total_prev = int(qdf["clicks_prev"].sum())
    change = total_curr - total_prev
    pct = (change / total_prev * 100) if total_prev else 0

    path = selected_page.replace(SITE_DOMAIN, "")
    st.markdown(
        f"**Page:** `{path}` &nbsp;|&nbsp; "
        f"**Current clicks:** {total_curr:,} &nbsp;|&nbsp; "
        f"**Previous clicks:** {total_prev:,} &nbsp;|&nbsp; "
        f"**Change:** {change:+,} ({pct:+.1f}%)")
    st.divider()

    total_q = len(qdf)
    new_q = len(qdf[qdf["status"] == "New"])
    lost_q = len(qdf[qdf["status"] == "Lost"])
    net = new_q - lost_q
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total queries", f"{total_q:,}")
    c2.metric("🆕 New", f"{new_q:,}")
    c3.metric("❌ Lost", f"{lost_q:,}")
    c4.metric("Net query change", f"{net:+,}", delta=f"{net:+,}", delta_color="normal")
    st.divider()

    st.subheader("Query data")
    status_filter = st.multiselect("Filter by status", ["New", "Lost", "Retained"],
                                    default=["New", "Lost", "Retained"])
    filtered = qdf[qdf["status"].isin(status_filter)]

    display = pd.DataFrame({
        "Query": filtered["query"], "Status": filtered["status"],
        "Clicks (curr)": filtered["clicks_curr"], "Clicks (prev)": filtered["clicks_prev"],
        "Click Δ": filtered["clicks_change"],
        "Impr (curr)": filtered["impr_curr"], "Impr (prev)": filtered["impr_prev"],
        "Impr Δ": filtered["impr_change"],
        "Pos (curr)": filtered["pos_curr"], "Pos (prev)": filtered["pos_prev"],
        "Pos Δ": filtered["pos_change"],
    })

    sty = display.style.map(
        lambda v: f"color:{BRAND_GREEN};font-weight:600" if isinstance(v, (int, float)) and v > 0
        else (f"color:{BRAND_RED};font-weight:600" if isinstance(v, (int, float)) and v < 0 else ""),
        subset=["Click Δ", "Impr Δ"])
    st.dataframe(sty, use_container_width=True, hide_index=True, column_config={
        "Query": st.column_config.TextColumn(width="large"),
        "Pos (curr)": st.column_config.NumberColumn(format="%.1f"),
        "Pos (prev)": st.column_config.NumberColumn(format="%.1f"),
        "Pos Δ": st.column_config.NumberColumn(format="%.1f"),
    })

    if len(qdf) >= 1000:
        st.caption("Top 1,000 queries by clicks shown.")

    slug = path.rstrip("/").split("/")[-1][:30]
    meta = f"Binaytara SEO Monitor | Page: {path} | {cs} to {ce} vs {ps} to {pe}"
    xlsx = to_excel_bytes(display, "Keywords", meta)
    st.download_button("⬇ Export keywords", data=xlsx,
                       file_name=f"binaytara_keywords_{slug}_{cs}_to_{ce}.xlsx",
                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    st.divider()

    # Position distribution
    retained = filtered[filtered["status"] == "Retained"].copy()
    if not retained.empty and retained["pos_curr"].notna().any():
        st.subheader("Position distribution (retained queries)")
        pos = retained["pos_curr"].dropna()
        def _bucket(p):
            if p <= 3: return "1–3 (Top 3)"
            if p <= 10: return "4–10 (Page 1)"
            if p <= 20: return "11–20 (Page 2)"
            if p <= 50: return "21–50"
            return "51+"
        bc = pos.apply(_bucket).value_counts().reindex(
            ["1–3 (Top 3)", "4–10 (Page 1)", "11–20 (Page 2)", "21–50", "51+"], fill_value=0)
        fig = px.bar(x=bc.index, y=bc.values, labels={"x": "Position", "y": "Queries"},
                     color_discrete_sequence=[BRAND_NAVY])
        fig.update_layout(height=300, margin=dict(l=40, r=20, t=20, b=30), showlegend=False)
        st.plotly_chart(fig, use_container_width=True)

    st.caption("GSC verification: Performance → Pages → filter by this URL → compare date ranges")
