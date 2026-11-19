"""
Binaytara SEO Monitor v3 — Tab: Pages
Page table with growth-first default sort, inline query drill-down,
and per-page daily trend on demand.
"""
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from config import BRAND_NAVY, BRAND_GREEN, BRAND_RED, BRAND_GRAY, SITE_DOMAIN
from data.processing import join_ga4_gsc, signal_label, resample_timeseries
from export import to_excel_bytes, make_filename

def render(dates, organic_only, section_filter, controls=None):
    from data.ga4 import fetch_page_traffic, fetch_page_daily_ga4
    from data.gsc import fetch_gsc_page_summary, fetch_page_daily_gsc, fetch_gsc_queries_for_page

    controls = controls or {}
    gran = controls.get("granularity", "Daily")
    cs, ce = dates["curr_start"], dates["curr_end"]
    ps, pe = dates["prev_start"], dates["prev_end"]
    show_cmp = dates.get("show_comparison", True)

    with st.spinner("Loading page data..."):
        curr_pages = fetch_page_traffic(cs, ce, organic_only)
        prev_pages = fetch_page_traffic(ps, pe, organic_only) if show_cmp else pd.DataFrame()
        gsc_data = fetch_gsc_page_summary(cs, ce)

    if curr_pages.empty:
        st.warning("No page data for this range.")
        return

    table = curr_pages[["page_path","section","totalUsers","sessions"]].copy()
    table.rename(columns={"totalUsers":"users_current","sessions":"sessions_current"}, inplace=True)

    if show_cmp and not prev_pages.empty:
        prev_agg = prev_pages[["page_path","totalUsers"]].rename(columns={"totalUsers":"users_previous"})
        table = table.merge(prev_agg, on="page_path", how="left").fillna(0)
        table["users_previous"] = table["users_previous"].astype(int)
        table["users_change"] = table["users_current"] - table["users_previous"]
        table["users_pct_change"] = table.apply(
            lambda r: (r["users_change"]/r["users_previous"]*100) if r["users_previous"]>0 else None, axis=1)
        table["signal"] = table.apply(lambda r: signal_label(r["users_current"], r["users_previous"]), axis=1)

    table = join_ga4_gsc(table, gsc_data)

    if section_filter and "All Sections" not in section_filter:
        table = table[table["section"].isin(section_filter)]

    # ── Sort options: growth first as default ─────────────────────
    st.subheader("Page Performance Table")
    search = st.text_input("🔍 Filter by page path", placeholder="e.g. cancernews, stomach-cancer")
    if search: table = table[table["page_path"].str.contains(search, case=False, na=False)]

    sort_opts = ["Users Change (biggest growth first)", "Users Change (biggest drops first)",
                 "Current Users (highest first)", "GSC Impressions (highest first)", "GSC CTR (lowest first)"]
    sort_col = st.selectbox("Sort by", sort_opts, index=0)
    sort_map = {"Users Change (biggest growth first)": ("users_change", False),
                "Users Change (biggest drops first)": ("users_change", True),
                "Current Users (highest first)": ("users_current", False),
                "GSC Impressions (highest first)": ("gsc_impressions", False),
                "GSC CTR (lowest first)": ("gsc_ctr", True)}
    col, asc = sort_map.get(sort_col, ("users_current", False))
    if col in table.columns: table = table.sort_values(col, ascending=asc)

    show_cols = ["page_path","section","users_current","sessions_current"]
    if show_cmp and "users_change" in table.columns:
        show_cols += ["users_previous","users_change","users_pct_change","signal"]
    for g in ["gsc_clicks","gsc_impressions","gsc_ctr","gsc_position"]:
        if g in table.columns: show_cols.append(g)

    rename = {"page_path":"Page","section":"Section","users_current":"Users","sessions_current":"Sessions",
              "users_previous":"Prev Users","users_change":"Change","users_pct_change":"% Change",
              "signal":"Signal","gsc_clicks":"Clicks","gsc_impressions":"Impressions",
              "gsc_ctr":"CTR","gsc_position":"Avg Pos"}
    disp = table[[c for c in show_cols if c in table.columns]].head(100).rename(columns=rename)

    col_config = {"Page": st.column_config.TextColumn(width="large")}
    if "CTR" in disp.columns: col_config["CTR"] = st.column_config.NumberColumn(format="%.2f%%")
    if "Avg Pos" in disp.columns: col_config["Avg Pos"] = st.column_config.NumberColumn(format="%.1f")
    if "% Change" in disp.columns: col_config["% Change"] = st.column_config.NumberColumn(format="%+.0f%%")
    st.dataframe(disp, use_container_width=True, hide_index=True, column_config=col_config)

    xlsx = to_excel_bytes(table[[c for c in show_cols if c in table.columns]].rename(columns=rename),
                          "Pages", f"Binaytara SEO Monitor | {cs} to {ce}")
    st.download_button("⬇ Export page table", data=xlsx,
                       file_name=make_filename("pages", cs, ce),
                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    st.divider()

    # ── Per-page daily trend (on demand) ──────────────────────────
    st.subheader("📈 Page trend: daily/weekly traffic for a single page")
    st.caption("Select a page to load its daily traffic from GA4 and GSC. One lightweight API call per source.")
    page_options = table["page_path"].head(200).tolist()
    if page_options:
        selected_page = st.selectbox("Page path", page_options, index=0, key="page_trend_select")
        if selected_page and st.button("Load page trend", key="load_page_trend"):
            full_url = SITE_DOMAIN + selected_page
            with st.spinner(f"Loading trend for {selected_page[:50]}..."):
                pg_ga = fetch_page_daily_ga4(cs, ce, selected_page, organic_only)
                pg_gsc = fetch_page_daily_gsc(full_url, cs, ce)

            fig = go.Figure()
            if not pg_ga.empty:
                rs = resample_timeseries(pg_ga.rename(columns={"totalUsers":"users"}), "date", gran, ["users"])
                fig.add_trace(go.Scatter(x=rs["date"], y=rs["users"], name="GA4 users",
                                         line=dict(color=BRAND_GREEN, width=2)))
            if not pg_gsc.empty:
                rs2 = resample_timeseries(pg_gsc, "date", gran, ["clicks","impressions"])
                fig.add_trace(go.Scatter(x=rs2["date"], y=rs2["clicks"], name="GSC clicks",
                                         line=dict(color=BRAND_NAVY, width=2)))
                fig.add_trace(go.Scatter(x=rs2["date"], y=rs2["impressions"], name="GSC impressions",
                                         line=dict(color=BRAND_GRAY, width=1.5, dash="dot"), yaxis="y2"))
            fig.update_layout(height=350, hovermode="x unified",
                legend=dict(orientation="h", y=1.02, x=1, xanchor="right"),
                margin=dict(l=40,r=50,t=20,b=30),
                yaxis=dict(title="Users / Clicks"),
                yaxis2=dict(title="Impressions", overlaying="y", side="right", showgrid=False))
            st.plotly_chart(fig, use_container_width=True)
            st.caption(f"Traffic for `{selected_page}`. GA4 users = all organic engines; "
                       "GSC clicks/impressions = Google only.")

            # Show queries for this page too
            with st.expander("View queries for this page"):
                with st.spinner("Loading queries..."):
                    qdf = fetch_gsc_queries_for_page(full_url, cs, ce)
                if qdf.empty:
                    st.info("No query data returned.")
                else:
                    st.dataframe(qdf.sort_values("clicks", ascending=False).head(30),
                                 use_container_width=True, hide_index=True)
    else:
        st.info("No pages to show with current filters.")
