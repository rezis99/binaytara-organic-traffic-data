"""
Binaytara SEO Monitor v3.2 — Main Application
"""
import streamlit as st
import pandas as pd
from datetime import date, timedelta
from config import (
    DATE_PRESETS, DATA_LAG_DAYS, DEFAULT_PRESET, BRAND_NAVY, BRAND_GREEN, BRAND_RED,
    SECTIONS, DEFAULT_SECTION, GRANULARITY_OPTIONS, SMOOTHING_OPTIONS,
)

st.set_page_config(page_title="Binaytara SEO Monitor", page_icon="📊",
                   layout="wide", initial_sidebar_state="expanded")
st.markdown(f"""<style>
.stMetric {{ background:{BRAND_NAVY}08; padding:12px 16px; border-radius:8px; border-left:4px solid {BRAND_NAVY}; }}
.stTabs [data-baseweb="tab"] {{ padding:8px 18px; font-weight:500; }}
div[data-testid="stMetricValue"] {{ font-size:1.5rem; font-weight:600; }}
</style>""", unsafe_allow_html=True)

# ── Sidebar ───────────────────────────────────────────────────────
with st.sidebar:
    st.markdown(f'<h2 style="color:{BRAND_NAVY};margin-bottom:0;">📊 Binaytara</h2>', unsafe_allow_html=True)
    st.markdown('<p style="color:#666;font-size:13px;margin-top:0;">SEO Monitor v3.2</p>', unsafe_allow_html=True)
    st.divider()

    st.markdown("**📅 Date range**")
    all_presets = list(DATE_PRESETS.keys()) + ["Specific dates"]
    preset = st.selectbox("Period", all_presets,
                          index=list(DATE_PRESETS.keys()).index(DEFAULT_PRESET))
    today = date.today()
    safe_end = today - timedelta(days=DATA_LAG_DAYS)

    if preset == "Custom":
        a,b = st.columns(2)
        with a: curr_start = st.date_input("Current start", value=safe_end-timedelta(days=27), max_value=safe_end)
        with b: curr_end = st.date_input("Current end", value=safe_end, max_value=safe_end)
        c,d = st.columns(2)
        with c: prev_start = st.date_input("Compare start",
                    value=curr_start-timedelta(days=(curr_end-curr_start).days+1), max_value=safe_end)
        with d: prev_end = st.date_input("Compare end", value=curr_start-timedelta(days=1), max_value=safe_end)
    elif preset == "Specific dates":
        st.caption("Compare two specific dates (e.g., Oct 30 vs Nov 13)")
        a,b = st.columns(2)
        with a: date_a = st.date_input("Date A", value=safe_end-timedelta(days=14), max_value=safe_end)
        with b: date_b = st.date_input("Date B", value=safe_end, max_value=safe_end)
        curr_start, curr_end = date_b, date_b
        prev_start, prev_end = date_a, date_a
        st.caption(f"Comparing {date_a} vs {date_b}")
    else:
        days = DATE_PRESETS[preset]
        curr_end = safe_end
        curr_start = safe_end - timedelta(days=days-1)
        prev_end = curr_start - timedelta(days=1)
        prev_start = prev_end - timedelta(days=days-1)
        st.caption(f"Current: {curr_start} to {curr_end}")
        st.caption(f"Compare: {prev_start} to {prev_end}")

    dates = {"curr_start": str(curr_start), "curr_end": str(curr_end),
             "prev_start": str(prev_start), "prev_end": str(prev_end)}
    show_comparison = st.checkbox("Compare with previous period", value=True)
    dates["show_comparison"] = show_comparison
    st.divider()

    st.markdown("**📈 Chart controls**")
    granularity = st.radio("Granularity", GRANULARITY_OPTIONS, index=0, horizontal=True)
    smoothing = st.selectbox("Smoothing (daily only)", SMOOTHING_OPTIONS, index=0)
    st.divider()

    # Traffic type: multi-select from GA4 channel groups
    st.markdown("**📊 Traffic channels**")
    CHANNEL_OPTIONS = [
        "Organic Search", "Direct", "Referral", "Organic Social",
        "Paid Search", "Paid Other", "Cross-network", "Email",
        "AI Assistant", "Organic Video", "Organic Shopping", "Paid Social",
    ]
    selected_channels = st.multiselect(
        "Show these channels", CHANNEL_OPTIONS, default=["Organic Search"],
        help="Select one or more GA4 channel groups. 'Organic Search' = all search engines. "
             "Check multiple to overlay them on the charts.")
    if not selected_channels:
        selected_channels = ["Organic Search"]

    organic_only = selected_channels == ["Organic Search"]
    controls = {"granularity": granularity, "smoothing": smoothing,
                "selected_channels": selected_channels}

    # Build human-readable label
    if len(selected_channels) == 1:
        traffic_label = selected_channels[0]
    elif len(selected_channels) <= 3:
        traffic_label = " + ".join(selected_channels)
    else:
        traffic_label = f"{len(selected_channels)} channels"
    st.caption(f"Showing: {traffic_label}")
    st.divider()

    st.markdown("**🏷 Sections**")
    section_names = ["All Sections"] + [s["name"] for s in SECTIONS] + [DEFAULT_SECTION]
    section_filter = st.multiselect("Study these sections", section_names, default=["All Sections"])
    if not section_filter: section_filter = ["All Sections"]
    st.divider()

    if st.button("🔄 Refresh data", use_container_width=True):
        st.cache_data.clear(); st.rerun()
    st.divider()
    st.caption(f"Data as of: {safe_end} (recent {DATA_LAG_DAYS} days excluded)")

# ── Lazy MTD ──────────────────────────────────────────────────────
from utils import mtd_ranges
mtd = mtd_ranges(DATA_LAG_DAYS)
with st.expander(f"📅 **Month-to-date: {mtd['month_name']}** — day {mtd['safe_day']} of "
                 f"{mtd['days_in_month']} ({mtd['days_remaining']} remaining)", expanded=False):
    try:
        from data.ga4 import fetch_users_total_ga4
        from data.gsc import fetch_gsc_daily_totals
        # GA4 users: query each range directly (dimensionless) so GA4 returns its own
        # deduplicated count — summing daily totals would double-count repeat visitors.
        tu = fetch_users_total_ga4(mtd["this_start"], mtd["this_end"], True)
        pu = fetch_users_total_ga4(mtd["last_mtd_start"], mtd["last_mtd_end"], True)
        fu = fetch_users_total_ga4(mtd["last_full_start"], mtd["last_full_end"], True)
        # GSC clicks: a plain count, not a unique-person metric, so summing daily is accurate.
        mtd_gsc = fetch_gsc_daily_totals(mtd["this_start"], mtd["this_end"])
        prev_gsc = fetch_gsc_daily_totals(mtd["last_mtd_start"], mtd["last_mtd_end"])
        full_gsc = fetch_gsc_daily_totals(mtd["last_full_start"], mtd["last_full_end"])
        def _s(df,c): return int(pd.to_numeric(df[c],errors="coerce").fillna(0).sum()) if not df.empty and c in df.columns else 0
        tc=_s(mtd_gsc,"clicks"); pc_=_s(prev_gsc,"clicks"); fc=_s(full_gsc,"clicks")
        proj_u=int(tu/mtd["days_elapsed"]*mtd["days_in_month"]) if mtd["days_elapsed"] else 0
        proj_c=int(tc/mtd["days_elapsed"]*mtd["days_in_month"]) if mtd["days_elapsed"] else 0
        def _cp(c,p):
            if not p: return ""
            d=(c-p)/p*100; color=BRAND_GREEN if d>=0 else BRAND_RED
            return f' <span style="color:{color};font-weight:600;">({d:+.0f}%)</span>'
        m1,m2,m3,m4=st.columns(4)
        with m1:
            st.markdown("**GA4 organic users**")
            st.markdown(f"This month: **{tu:,}**{_cp(tu,pu)}", unsafe_allow_html=True)
            st.markdown(f"{mtd['prev_month_name']} day {mtd['safe_day']}: {pu:,}")
        with m2:
            st.markdown("**GSC clicks (Google)**")
            st.markdown(f"This month: **{tc:,}**{_cp(tc,pc_)}", unsafe_allow_html=True)
            st.markdown(f"{mtd['prev_month_name']} day {mtd['safe_day']}: {pc_:,}")
        with m3:
            st.markdown("**Projected month-end**")
            st.markdown(f"Users: **{proj_u:,}**{_cp(proj_u,fu)}", unsafe_allow_html=True)
            st.markdown(f"Clicks: **{proj_c:,}**{_cp(proj_c,fc)}", unsafe_allow_html=True)
        with m4:
            st.markdown(f"**{mtd['prev_month_name']} actual**")
            st.markdown(f"Users: {fu:,}"); st.markdown(f"Clicks: {fc:,}")
        st.caption(f"GA4 user figures are true deduplicated totals for each exact date range (match GA4 "
                   f"Explore for the same range and filter). GSC clicks are summed from daily values "
                   f"(valid, since clicks aren't a unique-person metric). "
                   f"Pace = total so far ÷ {mtd['days_elapsed']} days × {mtd['days_in_month']} days — "
                   f"the projection itself is an estimate, not a dedup total, since it assumes the rest "
                   f"of the month behaves like the days so far. Last included day: {mtd['this_end']}.")
    except Exception as e:
        st.warning(f"Could not load MTD: {e}. Click Refresh to retry.")

# ── Header ────────────────────────────────────────────────────────
scope = "All sections" if "All Sections" in section_filter else " + ".join(section_filter)
state = (f'{traffic_label} · {granularity} · {dates["curr_start"]} to {dates["curr_end"]}'
         f'{" vs "+dates["prev_start"]+" to "+dates["prev_end"] if show_comparison else ""} · {scope}')
st.markdown(f'<h1 style="color:{BRAND_NAVY};font-size:1.7rem;margin-bottom:2px;">Binaytara SEO Monitor</h1>',
            unsafe_allow_html=True)
st.markdown(f'<p style="color:#666;font-size:13px;margin-top:0;">{state}</p>', unsafe_allow_html=True)

# ── Tabs ──────────────────────────────────────────────────────────
tab1,tab2,tab3,tab4,tab5 = st.tabs([
    "📈 Overview","🔎 Search Performance","📄 Pages","🧭 Keyword Deep Dive","💡 Opportunities"])
try:
    with tab1:
        from tabs.overview import render as r1
        r1(dates, organic_only, section_filter, controls)
    with tab2:
        from tabs.search_performance import render as r2
        r2(dates, organic_only, section_filter, controls)
    with tab3:
        from tabs.pages import render as r3
        r3(dates, organic_only, section_filter, controls)
    with tab4:
        from tabs.keywords import render as r4
        r4(dates, organic_only, section_filter)
    with tab5:
        from tabs.opportunities import render as r5
        r5(dates, organic_only, section_filter)
except Exception as e:
    st.error(f"Error: {e}")
    st.caption("If SSL error, click Refresh (retries up to 3 times).")
    with st.expander("Details"):
        import traceback; st.code(traceback.format_exc())

# ── Export All ────────────────────────────────────────────────────
st.divider()
st.subheader("⬇ Export all dashboard data")
st.caption("One Excel file with every table from every tab. Each sheet is labeled so an AI or analyst "
           "can read it without confusion. No data shown on screen is left out.")
if st.button("📥 Generate full export", use_container_width=True):
    from export import multi_sheet_excel
    with st.spinner("Collecting all data..."):
        sheets = {}
        try:
            from data.ga4 import (fetch_daily_traffic, fetch_page_traffic, fetch_country_traffic,
                                  fetch_section_daily_ga4, fetch_mainsite_daily_ga4)
            from data.gsc import (fetch_gsc_daily_totals, fetch_gsc_page_summary,
                                  fetch_gsc_query_totals, fetch_gsc_device_totals,
                                  fetch_section_daily_gsc)
            from data.processing import join_ga4_gsc, classify_section
            cs,ce = dates["curr_start"], dates["curr_end"]
            ps,pe = dates["prev_start"], dates["prev_end"]

            # Sheet 1: Daily organic traffic
            d1 = fetch_daily_traffic(cs,ce,True)
            if not d1.empty: sheets["Daily Organic Users"] = d1

            # Sheet 2: Daily total traffic
            d1t = fetch_daily_traffic(cs,ce,False)
            if not d1t.empty: sheets["Daily Total Users"] = d1t

            # Sheet 3: Daily GSC totals
            d2 = fetch_gsc_daily_totals(cs,ce)
            if not d2.empty: sheets["Daily GSC Totals"] = d2

            # Sheet 4: Page performance with changes
            pc = fetch_page_traffic(cs,ce,organic_only)
            gsc_pc = fetch_gsc_page_summary(cs,ce)
            if not pc.empty:
                joined = join_ga4_gsc(pc, gsc_pc)
                if show_comparison:
                    pp = fetch_page_traffic(ps,pe,organic_only)
                    if not pp.empty:
                        prev_agg = pp[["page_path","totalUsers"]].rename(columns={"totalUsers":"users_previous"})
                        joined = joined.merge(prev_agg, on="page_path", how="left").fillna(0)
                        joined["users_previous"] = joined["users_previous"].astype(int)
                        joined["users_change"] = joined["totalUsers"] - joined["users_previous"]
                        joined["pct_change"] = joined.apply(
                            lambda r: round((r["users_change"]/r["users_previous"])*100,1) if r["users_previous"]>0 else None, axis=1)
                sheets["Page Performance"] = joined.sort_values(
                    "users_change" if "users_change" in joined.columns else "totalUsers", ascending=True)

            # Sheet 5: Section summary
            # Note: users per section is a sum of per-page users within that section.
            # A user visiting 3 pages in TCN counts 3 times in TCN's total. This is how
            # GA4's page-path dimension works (each page row is independently deduped).
            # The section sums will add up to MORE than the true site-wide dedup total.
            if not pc.empty:
                sec = pc.groupby("section", as_index=False).agg(
                    users=("totalUsers","sum"), sessions=("sessions","sum"), pages=("page_path","count"))
                total_u = sec["users"].sum()
                sec["user_share_pct"] = (sec["users"]/total_u*100).round(1) if total_u else 0
                sec["note"] = "Users = sum of per-page users (a multi-page visitor counts once per page)"
                sheets["Section Summary"] = sec.sort_values("users", ascending=False)

            # Sheet 6: Section daily trends (GA4)
            from config import SECTIONS
            sec_rows = []
            for s in SECTIONS:
                sd = fetch_section_daily_ga4(cs,ce,s["prefix"],True)
                if not sd.empty:
                    sd = sd.copy()
                    sd["section"] = s["name"]
                    sec_rows.append(sd)
            ms = fetch_mainsite_daily_ga4(cs,ce,True)
            if not ms.empty:
                ms = ms.copy()
                ms["section"] = "Main Site"
                sec_rows.append(ms)
            if sec_rows:
                sheets["Section Daily GA4"] = pd.concat(sec_rows, ignore_index=True)

            # Sheet 7: Section daily trends (GSC)
            gsc_sec_rows = []
            for s in SECTIONS:
                gsd = fetch_section_daily_gsc(cs,ce,s["gsc_pattern"])
                if not gsd.empty:
                    gsd = gsd.copy()
                    gsd["section"] = s["name"]
                    gsc_sec_rows.append(gsd)
            if gsc_sec_rows:
                sheets["Section Daily GSC"] = pd.concat(gsc_sec_rows, ignore_index=True)

            # Sheet 8: GSC queries
            q = fetch_gsc_query_totals(cs,ce)
            if not q.empty: sheets["GSC Queries (top 5K)"] = q.head(5000)

            # Sheet 9: Device
            dev = fetch_gsc_device_totals(cs,ce)
            if not dev.empty:
                total_cl = dev["clicks"].sum()
                dev["click_share_pct"] = (dev["clicks"]/total_cl*100).round(1) if total_cl else 0
                sheets["Device Split"] = dev

            # Sheet 10: Country
            ctr = fetch_country_traffic(cs,ce,True)
            if not ctr.empty:
                total_cu = ctr["totalUsers"].sum()
                ctr["user_share_pct"] = (ctr["totalUsers"]/total_cu*100).round(1) if total_cu else 0
                sheets["Country Traffic"] = ctr

            # Sheet 11: Previous period page data (for AI comparison)
            if show_comparison:
                pp2 = fetch_page_traffic(ps,pe,organic_only)
                if not pp2.empty:
                    sheets["Prev Period Pages"] = pp2

            # Sheet 12: Previous period GSC queries
            if show_comparison:
                qp = fetch_gsc_query_totals(ps,pe)
                if not qp.empty: sheets["Prev Period Queries"] = qp.head(5000)

        except Exception as ex:
            st.error(f"Export error: {ex}")

        if sheets:
            meta = f"Binaytara SEO Monitor | {cs} to {ce} vs {ps} to {pe} | Generated {date.today()} | Channels: {traffic_label}"
            xlsx = multi_sheet_excel(sheets, meta)
            st.download_button("⬇ Download full export (.xlsx)", data=xlsx,
                               file_name=f"binaytara_seo_full_export_{cs}_to_{ce}.xlsx",
                               mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                               use_container_width=True)
            st.caption(f"Contains {len(sheets)} sheets: {', '.join(sheets.keys())}")
        else:
            st.warning("No data to export.")
