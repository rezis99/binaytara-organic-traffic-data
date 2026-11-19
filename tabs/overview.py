"""
Binaytara SEO Monitor v3 — Tab: Overview
Scorecards, rolling hero, exact trend, section-over-time (lightweight),
decline drill-down with inline query expanders, geography.
"""
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from config import (BRAND_NAVY, BRAND_GREEN, BRAND_RED, BRAND_GRAY, BRAND_LIGHT_BLUE,
                    SECTION_COLORS, SECTIONS, DEFAULT_SECTION, ROLLING_WINDOW_DAYS, SITE_DOMAIN,
                    DATA_LAG_DAYS)
from data.processing import (
    join_ga4_gsc, rolling_total, resample_timeseries, apply_smoothing,
    normalize_path, classify_section,
)
from export import to_excel_bytes, make_filename

def _nz(s): return pd.to_numeric(s, errors="coerce").fillna(0)
def _wmean(df, col, w):
    t = df[w].sum(); return (df[col]*df[w]).sum()/t if t else None
def _pct(c,p):
    if not p: return None
    return (c-p)/p*100
def _color_pct(v):
    if v is None: return ""
    c = BRAND_GREEN if v >= 0 else BRAND_RED
    return f' <span style="color:{c};font-weight:600;">({v:+.0f}%)</span>'

def render(dates, organic_only, section_filter, controls=None):
    from data.ga4 import (fetch_daily_traffic, fetch_page_traffic,
                          fetch_section_daily_ga4, fetch_mainsite_daily_ga4, fetch_country_traffic)
    from data.gsc import (fetch_gsc_daily_totals, fetch_gsc_page_summary,
                          fetch_section_daily_gsc, fetch_gsc_queries_for_page)

    controls = controls or {}
    gran = controls.get("granularity", "Daily")
    smooth = controls.get("smoothing", "Raw")
    # NOTE: the backend currently only distinguishes two states — "Organic Search
    # only" (organic_only=True) or "all channels combined" (organic_only=False).
    # It cannot yet isolate an arbitrary subset (e.g. exactly Organic + Direct).
    # These two flags reflect that real backend behavior, so the chart never
    # silently shows something different from what was actually fetched.
    show_organic = organic_only
    show_total = not organic_only

    cs, ce = dates["curr_start"], dates["curr_end"]
    ps, pe = dates["prev_start"], dates["prev_end"]
    show_cmp = dates.get("show_comparison", True)

    with st.spinner("Loading overview..."):
        gsc_daily = fetch_gsc_daily_totals(cs, ce)
        ga_daily_org = fetch_daily_traffic(cs, ce, True) if show_organic else pd.DataFrame()
        ga_daily_tot = fetch_daily_traffic(cs, ce, False) if show_total else pd.DataFrame()
        pages_c = fetch_page_traffic(cs, ce, organic_only)
        gsc_pages_c = fetch_gsc_page_summary(cs, ce)
        if show_cmp:
            pages_p = fetch_page_traffic(ps, pe, organic_only)
            gsc_pages_p = fetch_gsc_page_summary(ps, pe)
        else:
            pages_p, gsc_pages_p = pd.DataFrame(), pd.DataFrame()

    if ga_daily_org.empty and ga_daily_tot.empty and gsc_daily.empty:
        st.warning("No data for this range. Check GA4/GSC access and dates.")
        return

    # ── Scorecards ────────────────────────────────────────────────
    # GA4 users: use true deduplicated range total (matches GA4 Explore exactly).
    # GSC clicks/impressions: sum from page-level data (clicks are additive, not unique-person).
    from data.ga4 import fetch_users_total_ga4
    joined_c = join_ga4_gsc(pages_c[["page_path","section","totalUsers","sessions"]].rename(
        columns={"totalUsers":"users"}), gsc_pages_c)
    cur = {
        "users": fetch_users_total_ga4(cs, ce, organic_only),
        "clicks": int(_nz(joined_c.get("gsc_clicks", pd.Series(dtype=float))).sum()),
        "impr": int(_nz(joined_c.get("gsc_impressions", pd.Series(dtype=float))).sum()),
    }
    cur["ctr"] = (cur["clicks"]/cur["impr"]) if cur["impr"] else 0
    cur["pos"] = _wmean(joined_c.assign(_i=_nz(joined_c.get("gsc_impressions",0)),
                                         _p=_nz(joined_c.get("gsc_position",0))), "_p", "_i")

    prev = None
    if show_cmp and not pages_p.empty:
        joined_p = join_ga4_gsc(pages_p[["page_path","section","totalUsers","sessions"]].rename(
            columns={"totalUsers":"users"}), gsc_pages_p)
        prev = {
            "users": fetch_users_total_ga4(ps, pe, organic_only),
            "clicks": int(_nz(joined_p.get("gsc_clicks", pd.Series(dtype=float))).sum()),
            "impr": int(_nz(joined_p.get("gsc_impressions", pd.Series(dtype=float))).sum()),
        }
        prev["ctr"] = (prev["clicks"]/prev["impr"]) if prev["impr"] else 0
        prev["pos"] = _wmean(joined_p.assign(_i=_nz(joined_p.get("gsc_impressions",0)),
                                              _p=_nz(joined_p.get("gsc_position",0))), "_p", "_i")

    st.markdown("**Run rate**")
    c1,c2,c3,c4,c5 = st.columns(5)
    def _d(cur_v, prev_v):
        if not show_cmp or prev is None or prev_v in (None,0): return None, None
        return cur_v-prev_v, _pct(cur_v, prev_v)
    with c1:
        d,p = _d(cur["clicks"], prev["clicks"] if prev else None)
        st.metric("Clicks (Google)", f"{cur['clicks']:,}",
                  delta=f"{d:+,} ({p:+.0f}%)" if d is not None else None)
    with c2:
        d,p = _d(cur["users"], prev["users"] if prev else None)
        st.metric("Users (all organic)", f"{cur['users']:,}",
                  delta=f"{d:+,} ({p:+.0f}%)" if d is not None else None)
    with c3:
        d,p = _d(cur["impr"], prev["impr"] if prev else None)
        st.metric("Impressions", f"{cur['impr']:,}",
                  delta=f"{d:+,} ({p:+.0f}%)" if d is not None else None)
    with c4:
        if prev and show_cmp:
            dctr = (cur["ctr"]-prev["ctr"])*100
            st.metric("CTR", f"{cur['ctr']*100:.2f}%", delta=f"{dctr:+.2f} pts")
        else: st.metric("CTR", f"{cur['ctr']*100:.2f}%")
    with c5:
        if cur["pos"] is not None:
            if prev and show_cmp and prev["pos"] is not None:
                dp = cur["pos"]-prev["pos"]
                st.metric("Avg position", f"{cur['pos']:.1f}", delta=f"{dp:+.1f}", delta_color="inverse")
            else: st.metric("Avg position", f"{cur['pos']:.1f}")
        else: st.metric("Avg position", "—")

    st.caption("Clicks/impressions/CTR/position = Google Search Console (Google only). "
               "Users = GA4 organic (all search engines). Position is impression-weighted. "
               "Recent partial days excluded.")
    st.divider()

    # ── All-time history (like Ahrefs' full timeline) ───────────────
    with st.expander("📊 **All-time traffic history** (longest available real data)", expanded=False):
        st.caption("Unlike Ahrefs, which shows *estimated* traffic from keyword volumes × modeled CTR, "
                   "this chart uses **real data**: GA4 organic users (all search engines) going back to when "
                   "the GA4 property was created, and GSC clicks (Google only) going back ~16 months "
                   "(GSC's maximum retention). GA4 data may go further back than GSC. "
                   "**Method:** each GA4 monthly bar comes from one query to GA4 for that exact calendar "
                   "month (GA4's own deduplicated user count for that month) — it is NOT a sum of daily "
                   "totals, because summing daily unique-user counts double-counts anyone who visits on "
                   "more than one day in the month. GSC clicks ARE summed from daily values, since clicks "
                   "are a plain count (not a unique-person metric) and summing them is accurate.")
        from datetime import date as _date, timedelta as _td
        from data.ga4 import fetch_monthly_traffic_ga4
        hist_end = str(_date.today() - _td(days=DATA_LAG_DAYS))
        hist_start_ga = "2020-01-01"  # GA4 returns empty for dates before property existed
        hist_start_gsc = str(_date.today() - _td(days=480))  # ~16 months

        with st.spinner("Loading all-time history (GA4 + GSC)..."):
            monthly_ga = fetch_monthly_traffic_ga4(hist_start_ga, hist_end, True)
            hist_gsc = fetch_gsc_daily_totals(hist_start_gsc, hist_end)

        hist_fig = go.Figure()
        if not monthly_ga.empty:
            hist_fig.add_trace(go.Bar(x=monthly_ga["date"], y=monthly_ga["totalUsers"],
                name="GA4 organic users (monthly, deduplicated)", marker_color=BRAND_GREEN, opacity=0.7))
        if not hist_gsc.empty:
            monthly_gsc = hist_gsc.set_index("date").resample("MS")["clicks"].sum().reset_index()
            hist_fig.add_trace(go.Bar(x=monthly_gsc["date"], y=monthly_gsc["clicks"],
                name="GSC clicks (monthly, summed)", marker_color=BRAND_NAVY, opacity=0.7))
        hist_fig.update_layout(barmode="group", height=350, hovermode="x unified",
            legend=dict(orientation="h", y=1.02, x=1, xanchor="right"),
            margin=dict(l=40,r=20,t=20,b=30), yaxis_title="Monthly total")
        st.plotly_chart(hist_fig, use_container_width=True)
        st.caption("GA4 goes back to property creation; GSC retains ~16 months. "
                   "GA4 bars: true monthly unique users, matches GA4 Explore for the same month and filter. "
                   "GSC bars: sum of daily clicks (valid, since clicks aren't deduplicated).")
    st.divider()

    # ── Hero: rolling 28-day total ────────────────────────────────
    st.subheader("Monthly-scale trend (rolling 28-day total)")
    hero = go.Figure()
    if not gsc_daily.empty:
        hero.add_trace(go.Scatter(x=gsc_daily["date"],
            y=rolling_total(gsc_daily["clicks"], ROLLING_WINDOW_DAYS),
            mode="lines", name="GSC clicks", line=dict(color=BRAND_NAVY, width=2.5)))
    if not ga_daily_org.empty:
        hero.add_trace(go.Scatter(x=ga_daily_org["date"],
            y=rolling_total(ga_daily_org["totalUsers"], ROLLING_WINDOW_DAYS),
            mode="lines", name="Organic users (all engines)", line=dict(color=BRAND_GREEN, width=2.5)))
    if show_total and not ga_daily_tot.empty:
        hero.add_trace(go.Scatter(x=ga_daily_tot["date"],
            y=rolling_total(ga_daily_tot["totalUsers"], ROLLING_WINDOW_DAYS),
            mode="lines", name="Total users (all channels combined)", line=dict(color=BRAND_GRAY, width=1.5, dash="dot")))
    hero.update_layout(height=380, hovermode="x unified",
        legend=dict(orientation="h", y=1.02, x=1, xanchor="right"),
        margin=dict(l=40,r=50,t=20,b=30), yaxis=dict(title="28-day total"))
    st.plotly_chart(hero, use_container_width=True)
    st.caption("Each point = sum of the trailing 28 daily values. This reads at monthly magnitude "
               "but, being a sum of daily unique-user counts, it will run somewhat higher than a true "
               "28-day deduplicated total (anyone visiting on multiple days gets counted once per day). "
               "Treat this chart as a trend line, not an exact unique-visitor count — for an exact total "
               "over any specific range, use the scorecards above or the All-time history section below, "
               "both of which query GA4 for a true deduplicated count. "
               "If more than one channel is selected in the sidebar, this line currently shows ALL "
               "channels combined, not only the selected subset (isolating an exact subset is not yet "
               "built). Begins 27 days after range start.")
    st.divider()

    # ── Exact trend ───────────────────────────────────────────────
    st.subheader(f"Exact trend — {gran.lower()}")
    exact = go.Figure()
    if not gsc_daily.empty:
        rs = resample_timeseries(gsc_daily, "date", gran, ["clicks","impressions"])
        y = apply_smoothing(rs["clicks"], smooth) if gran=="Daily" else rs["clicks"]
        exact.add_trace(go.Scatter(x=rs["date"], y=y, name="GSC clicks", line=dict(color=BRAND_NAVY, width=2)))
    if not ga_daily_org.empty:
        rs2 = resample_timeseries(ga_daily_org.rename(columns={"totalUsers":"users"}), "date", gran, ["users"])
        y2 = apply_smoothing(rs2["users"], smooth) if gran=="Daily" else rs2["users"]
        exact.add_trace(go.Scatter(x=rs2["date"], y=y2, name="Organic users", line=dict(color=BRAND_GREEN, width=2)))
    if show_total and not ga_daily_tot.empty:
        rs3 = resample_timeseries(ga_daily_tot.rename(columns={"totalUsers":"users_tot"}), "date", gran, ["users_tot"])
        y3 = apply_smoothing(rs3["users_tot"], smooth) if gran=="Daily" else rs3["users_tot"]
        exact.add_trace(go.Scatter(x=rs3["date"], y=y3, name="Total users", line=dict(color=BRAND_GRAY, width=1.5, dash="dot")))
    exact.update_layout(height=320, hovermode="x unified",
        legend=dict(orientation="h", y=1.02, x=1, xanchor="right"),
        margin=dict(l=40,r=20,t=20,b=30), yaxis_title="Count")
    st.plotly_chart(exact, use_container_width=True)
    st.divider()

    # ── What moved: FULL page list + drill-down ─────────────────────
    if show_cmp and not pages_p.empty:
        st.subheader("What moved: all pages that changed")
        pc = joined_c[["page_path","section","users"]].rename(columns={"users":"users_c"})
        pp = joined_p[["page_path","users"]].rename(columns={"users":"users_p"})
        movers = pc.merge(pp, on="page_path", how="outer")
        movers["section"] = movers.get("section", pd.Series(dtype=str)).fillna("Main Site")
        movers["users_c"] = _nz(movers["users_c"]).astype(int)
        movers["users_p"] = _nz(movers["users_p"]).astype(int)
        movers["change"] = movers["users_c"] - movers["users_p"]
        movers["pct_change"] = movers.apply(lambda r: _pct(r["users_c"], r["users_p"]), axis=1)
        movers = movers.drop_duplicates(subset=["page_path"])

        # Summary badges
        growing = movers[movers["change"]>0]
        declining = movers[movers["change"]<0]
        stable = movers[movers["change"]==0]
        s1,s2,s3 = st.columns(3)
        with s1: st.metric("📈 Growing pages", f"{len(growing):,}", delta=f"+{int(growing['change'].sum()):,} users total")
        with s2: st.metric("📉 Declining pages", f"{len(declining):,}", delta=f"{int(declining['change'].sum()):,} users total")
        with s3: st.metric("→ Stable pages", f"{len(stable):,}")

        # FULL sortable table (every page that moved)
        mover_sort = st.radio("Sort movers by", ["Biggest growth first","Biggest decline first","Biggest absolute change"],
                              index=0, horizontal=True, key="mover_sort")
        if mover_sort == "Biggest growth first":
            movers_sorted = movers.sort_values("change", ascending=False)
        elif mover_sort == "Biggest decline first":
            movers_sorted = movers.sort_values("change", ascending=True)
        else:
            movers_sorted = movers.assign(_abs=movers["change"].abs()).sort_values("_abs", ascending=False).drop(columns=["_abs"])

        # Exclude stable (change=0) unless user wants them
        show_stable = st.checkbox("Include pages with no change", value=False, key="show_stable")
        if not show_stable:
            movers_sorted = movers_sorted[movers_sorted["change"] != 0]

        disp_movers = movers_sorted[["page_path","section","users_c","users_p","change","pct_change"]].rename(
            columns={"page_path":"Page","section":"Section","users_c":"Current","users_p":"Previous",
                     "change":"Change","pct_change":"% Change"}).head(200)
        fmts = {"% Change": lambda v: f"{v:+.0f}%" if pd.notna(v) else "—"}
        sty = disp_movers.style.format(fmts).map(
            lambda v: f"color:{BRAND_GREEN};font-weight:600" if isinstance(v,(int,float)) and v>0
            else (f"color:{BRAND_RED};font-weight:600" if isinstance(v,(int,float)) and v<0 else ""),
            subset=["Change","% Change"])
        st.dataframe(sty, use_container_width=True, hide_index=True, height=400)
        st.caption(f"Showing {len(disp_movers)} of {len(movers_sorted)} pages. "
                   "Every page that gained or lost users is listed so no optimization opportunity is missed.")

        # Export movers
        from export import to_excel_bytes, make_filename
        movers_xlsx = to_excel_bytes(movers_sorted.rename(columns={
            "page_path":"Page","section":"Section","users_c":"Current","users_p":"Previous",
            "change":"Change","pct_change":"% Change"}),
            "All Movers", f"Binaytara SEO Monitor | {cs} to {ce}")
        st.download_button("⬇ Export all movers", data=movers_xlsx,
                           file_name=make_filename("all_movers", cs, ce),
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

        # Decline drill-down
        decliners = movers[movers["change"]<0].sort_values("change")
        # Inline query drill-down for declining pages
        if not decliners.empty:
            st.markdown("---")
            st.markdown("**🔍 Drill into a declining page: see which queries lost clicks**")
            st.caption("Select a declining page below. This fetches query data on demand (one API call per page).")
            dec_paths = decliners["page_path"].tolist()
            selected = st.selectbox("Declining page", dec_paths, key="decline_drilldown",
                                    format_func=lambda p: f"{p[:60]} ({int(movers[movers['page_path']==p]['change'].iloc[0]):+,} users)")
            if selected:
                full_url = SITE_DOMAIN + selected
                with st.spinner(f"Loading queries for {selected[:50]}..."):
                    q_curr = fetch_gsc_queries_for_page(full_url, cs, ce)
                    q_prev = fetch_gsc_queries_for_page(full_url, ps, pe)
                if q_curr.empty and q_prev.empty:
                    st.info("No query data returned for this page. GSC may anonymize low-volume queries.")
                else:
                    cm = {r["query"]:r for _,r in q_curr.iterrows()} if not q_curr.empty else {}
                    pm = {r["query"]:r for _,r in q_prev.iterrows()} if not q_prev.empty else {}
                    rows = []
                    for q in set(cm)|set(pm):
                        c,p = cm.get(q), pm.get(q)
                        cc = int(c["clicks"]) if c is not None else 0
                        pc_ = int(p["clicks"]) if p is not None else 0
                        ci = int(c["impressions"]) if c is not None else 0
                        pi_ = int(p["impressions"]) if p is not None else 0
                        cp = round(c["position"],1) if c is not None else None
                        pp_ = round(p["position"],1) if p is not None else None
                        status = "New" if p is None else ("Lost" if c is None else "Retained")
                        rows.append({"Query":q,"Status":status,"Clicks now":cc,"Clicks prev":pc_,
                                     "Click Δ":cc-pc_,"Impr now":ci,"Impr prev":pi_,"Impr Δ":ci-pi_,
                                     "Pos now":cp,"Pos prev":pp_})
                    qdf = pd.DataFrame(rows).sort_values("Click Δ", ascending=True)
                    lost = qdf[qdf["Click Δ"]<0]
                    gained = qdf[qdf["Click Δ"]>0]
                    if not lost.empty:
                        st.markdown(f"**Queries that lost clicks** ({len(lost)} queries)")
                        sty = lost.head(15).style.map(
                            lambda v: f"color:{BRAND_RED};font-weight:600" if isinstance(v,(int,float)) and v<0 else
                            (f"color:{BRAND_GREEN};font-weight:600" if isinstance(v,(int,float)) and v>0 else ""),
                            subset=["Click Δ","Impr Δ"])
                        st.dataframe(sty, use_container_width=True, hide_index=True)
                    if not gained.empty:
                        with st.expander(f"Queries that gained clicks ({len(gained)})"):
                            st.dataframe(gained.head(10), use_container_width=True, hide_index=True)
        st.divider()

    # ── Section over time (lightweight: 5 small API calls per source) ──
    st.subheader("Section trend over time")
    st.caption("Each section fetched separately (~180 rows each) instead of pulling all pages × all days.")
    sec_fig = go.Figure()
    for sec in SECTIONS:
        ga_sec = fetch_section_daily_ga4(cs, ce, sec["prefix"], organic_only)
        gsc_sec = fetch_section_daily_gsc(cs, ce, sec["gsc_pattern"])
        color = SECTION_COLORS.get(sec["name"], BRAND_GRAY)
        if not ga_sec.empty:
            rs = resample_timeseries(ga_sec.rename(columns={"totalUsers":"users"}), "date", gran, ["users"])
            sec_fig.add_trace(go.Scatter(x=rs["date"], y=rs["users"], name=f'{sec["name"]} (users)',
                                         line=dict(color=color, width=2)))
        if not gsc_sec.empty:
            rs2 = resample_timeseries(gsc_sec, "date", gran, ["clicks"])
            sec_fig.add_trace(go.Scatter(x=rs2["date"], y=rs2["clicks"], name=f'{sec["name"]} (clicks)',
                                         line=dict(color=color, width=1.5, dash="dot")))
    # Main Site
    ms_ga = fetch_mainsite_daily_ga4(cs, ce, organic_only)
    if not ms_ga.empty:
        rs3 = resample_timeseries(ms_ga.rename(columns={"totalUsers":"users"}), "date", gran, ["users"])
        sec_fig.add_trace(go.Scatter(x=rs3["date"], y=rs3["users"], name="Main Site (users)",
                                     line=dict(color=SECTION_COLORS["Main Site"], width=2)))
    sec_fig.update_layout(height=420, hovermode="x unified",
        legend=dict(orientation="h", y=1.02, x=1, xanchor="right"),
        margin=dict(l=40,r=20,t=20,b=30), yaxis_title="Count")
    st.plotly_chart(sec_fig, use_container_width=True)
    st.caption("Solid lines = GA4 organic users (all engines). Dotted lines = GSC clicks (Google only).")

    # Section summary table with share %
    if not joined_c.empty:
        sec_t = joined_c.groupby("section", as_index=False).agg(
            Users=("users","sum"), Clicks=("gsc_clicks","sum"))
        total_u = sec_t["Users"].sum()
        sec_t["User share %"] = (sec_t["Users"]/total_u*100).round(1) if total_u else 0
        total_cl = sec_t["Clicks"].sum()
        sec_t["Click share %"] = (sec_t["Clicks"]/total_cl*100).round(1) if total_cl else 0
        if show_cmp and not pages_p.empty:
            sec_p = joined_p.groupby("section", as_index=False).agg(Prev_users=("users","sum"))
            sec_t = sec_t.merge(sec_p, on="section", how="left").fillna({"Prev_users":0})
            sec_t["Change"] = sec_t["Users"] - sec_t["Prev_users"]
            sec_t["% change"] = sec_t.apply(lambda r: _pct(r["Users"], r["Prev_users"]), axis=1)
        sec_t = sec_t.sort_values("Users", ascending=False)
        st.dataframe(sec_t.style.format({
            "User share %": "{:.1f}%", "Click share %": "{:.1f}%",
            "% change": lambda v: f"{v:+.0f}%" if pd.notna(v) else "—"
        }).map(lambda v: f"color:{BRAND_GREEN};font-weight:600" if isinstance(v,(int,float)) and v>0
              else (f"color:{BRAND_RED};font-weight:600" if isinstance(v,(int,float)) and v<0 else ""),
              subset=[c for c in ["Change","% change"] if c in sec_t.columns]),
            use_container_width=True, hide_index=True)
        st.caption("**How to verify:** in GA4 Explore, set Rows = Page path, Values = Total users, "
                   "filter Session default channel group = Organic Search, then also filter Page path "
                   "begins with /cancernews (or /journal, etc.). The sum of that table's users column "
                   "will match this section's Users number. Note: a user who visits multiple pages "
                   "within the same section gets counted once per page, so section Users will sum to "
                   "more than the site-wide total in the scorecard above (which is a true site-wide dedup).")
        xlsx = to_excel_bytes(sec_t, "Section Split", f"Binaytara SEO Monitor | {cs} to {ce}")
        st.download_button("⬇ Export section split", data=xlsx,
                           file_name=make_filename("section_split", cs, ce),
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    st.divider()

    # ── Geography ─────────────────────────────────────────────────
    st.subheader("By country (GA4)")
    with st.spinner("Loading country data..."):
        ctr_c = fetch_country_traffic(cs, ce, organic_only)
        ctr_p = fetch_country_traffic(ps, pe, organic_only) if show_cmp else pd.DataFrame()
    if ctr_c.empty:
        st.info("No country data.")
    else:
        ct = ctr_c.rename(columns={"totalUsers":"Users"})[["country","Users"]]
        total = ct["Users"].sum()
        ct["Share %"] = (ct["Users"]/total*100).round(1) if total else 0
        if show_cmp and not ctr_p.empty:
            cp = ctr_p.rename(columns={"totalUsers":"Prev users"})[["country","Prev users"]]
            ct = ct.merge(cp, on="country", how="left").fillna({"Prev users":0})
            ct["Change"] = ct["Users"] - ct["Prev users"]
            ct["% change"] = ct.apply(lambda r: _pct(r["Users"], r["Prev users"]), axis=1)
        ct = ct.sort_values("Users", ascending=False)
        gl,gr = st.columns([2,3])
        with gl:
            fig = px.bar(ct.head(10).sort_values("Users"), x="Users", y="country", orientation="h",
                         color_discrete_sequence=[BRAND_NAVY])
            fig.update_layout(height=360, margin=dict(l=10,r=10,t=10,b=30))
            st.plotly_chart(fig, use_container_width=True)
        with gr:
            cols = [c for c in ["country","Users","Share %","Prev users","Change","% change"] if c in ct.columns]
            fmts = {"Share %": "{:.1f}%"}
            if "% change" in cols: fmts["% change"] = lambda v: f"{v:+.0f}%" if pd.notna(v) else "—"
            sty = ct.head(15)[cols].style.format(fmts)
            if "Change" in cols:
                sty = sty.map(lambda v: f"color:{BRAND_GREEN};font-weight:600" if isinstance(v,(int,float)) and v>0
                              else (f"color:{BRAND_RED};font-weight:600" if isinstance(v,(int,float)) and v<0 else ""),
                              subset=[c for c in ["Change","% change"] if c in cols])
            st.dataframe(sty, use_container_width=True, hide_index=True)
        xlsx = to_excel_bytes(ct, "Country", f"Binaytara SEO Monitor | {cs} to {ce}")
        st.download_button("⬇ Export country table", data=xlsx,
                           file_name=make_filename("country", cs, ce),
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
