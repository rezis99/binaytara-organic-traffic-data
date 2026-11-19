"""
Binaytara SEO Monitor v3 — GA4 Data Fetcher
Lightweight: section daily uses API-level filters. No bulk date×page pulls.
"""
import streamlit as st
import pandas as pd
from google.analytics.data_v1beta.types import (
    RunReportRequest, DateRange, Dimension, Metric,
    FilterExpression, FilterExpressionList, Filter,
)
from auth import ga4_client
from config import (GA4_PROPERTY_ID, GA4_ROW_LIMIT, CACHE_TTL_MAIN,
                    CACHE_TTL_QUERY, CACHE_MAX_ENTRIES)
from data.processing import normalize_path, classify_section
from utils import retry_on_ssl

_P = f"properties/{GA4_PROPERTY_ID}"

def _organic_filter():
    return FilterExpression(filter=Filter(
        field_name="sessionDefaultChannelGroup",
        string_filter=Filter.StringFilter(
            match_type=Filter.StringFilter.MatchType.EXACT, value="Organic Search")))

def _channel_filter(channels):
    """Build a filter for one or more GA4 channel groups.
    Single channel: exact match. Multiple: OR group."""
    if len(channels) == 1:
        return FilterExpression(filter=Filter(
            field_name="sessionDefaultChannelGroup",
            string_filter=Filter.StringFilter(
                match_type=Filter.StringFilter.MatchType.EXACT, value=channels[0])))
    # IN_LIST filter for multiple channels
    return FilterExpression(filter=Filter(
        field_name="sessionDefaultChannelGroup",
        in_list_filter=Filter.InListFilter(values=list(channels))))

def _path_prefix_filter(prefix):
    return FilterExpression(filter=Filter(
        field_name="pagePath",
        string_filter=Filter.StringFilter(
            match_type=Filter.StringFilter.MatchType.BEGINS_WITH, value=prefix)))

def _and_filters(*exprs):
    """Combine multiple FilterExpressions with AND logic."""
    return FilterExpression(and_group=FilterExpressionList(expressions=list(exprs)))

@retry_on_ssl(max_retries=3, delay=2.0)
def _run(dims, mets, start, end, dim_filter=None, limit=GA4_ROW_LIMIT):
    client = ga4_client()
    all_rows, offset = [], 0
    while True:
        req = RunReportRequest(
            property=_P, date_ranges=[DateRange(start_date=start, end_date=end)],
            dimensions=[Dimension(name=d) for d in dims],
            metrics=[Metric(name=m) for m in mets], limit=limit, offset=offset)
        if dim_filter: req.dimension_filter = dim_filter
        resp = client.run_report(req)
        for row in resp.rows:
            d = {}
            for i, dm in enumerate(dims): d[dm] = row.dimension_values[i].value
            for i, mt in enumerate(mets):
                v = row.metric_values[i].value
                try: d[mt] = int(v) if "." not in v else float(v)
                except: d[mt] = v
            all_rows.append(d)
        if len(resp.rows) < limit: break
        offset += limit
    return all_rows

# ── Tier 1: daily site totals (~180-365 rows) ──────────────────

@st.cache_data(ttl=CACHE_TTL_MAIN, max_entries=CACHE_MAX_ENTRIES, show_spinner=False)
def fetch_daily_traffic(start, end, organic_only=True):
    filt = _organic_filter() if organic_only else None
    rows = _run(["date"], ["totalUsers","sessions","newUsers","screenPageViews"], start, end, filt)
    if not rows: return pd.DataFrame(columns=["date","totalUsers","sessions","newUsers","screenPageViews"])
    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df["date"], format="%Y%m%d")
    for c in ["totalUsers","sessions","newUsers","screenPageViews"]:
        df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0).astype(int)
    df = df[(df["date"] >= pd.Timestamp(start)) & (df["date"] <= pd.Timestamp(end))]
    return df.sort_values("date").reset_index(drop=True)

# ── Tier 2: page summaries (~6K rows) ────────────────────────────

@st.cache_data(ttl=CACHE_TTL_MAIN, max_entries=CACHE_MAX_ENTRIES, show_spinner=False)
def fetch_page_traffic(start, end, organic_only=True):
    filt = _organic_filter() if organic_only else None
    rows = _run(["pagePath"], ["totalUsers","sessions","newUsers","engagementRate","averageSessionDuration"], start, end, filt)
    if not rows: return pd.DataFrame(columns=["page_path","section","totalUsers","sessions","newUsers","engagementRate","avgSessionDuration"])
    df = pd.DataFrame(rows)
    df.rename(columns={"pagePath":"page_path","averageSessionDuration":"avgSessionDuration"}, inplace=True)
    df["page_path"] = df["page_path"].apply(normalize_path)
    df = df[df["page_path"] != "(not set)"].copy()
    for c in ["totalUsers","sessions","newUsers"]: df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0).astype(int)
    df["engagementRate"] = pd.to_numeric(df["engagementRate"], errors="coerce").fillna(0)
    df["avgSessionDuration"] = pd.to_numeric(df["avgSessionDuration"], errors="coerce").fillna(0)
    df = df.groupby("page_path", as_index=False).agg({
        "totalUsers":"sum","sessions":"sum","newUsers":"sum","engagementRate":"mean","avgSessionDuration":"mean"})
    df["section"] = df["page_path"].apply(classify_section)
    return df.sort_values("totalUsers", ascending=False).reset_index(drop=True)

# ── Tier 2: section daily (LIGHTWEIGHT: ~180 rows per section) ──

@st.cache_data(ttl=CACHE_TTL_MAIN, max_entries=20, show_spinner=False)
def fetch_section_daily_ga4(start, end, section_prefix, organic_only=True):
    filters = [_path_prefix_filter(section_prefix)]
    if organic_only: filters.append(_organic_filter())
    filt = _and_filters(*filters) if len(filters) > 1 else filters[0]
    rows = _run(["date"], ["totalUsers"], start, end, filt)
    if not rows: return pd.DataFrame(columns=["date","totalUsers"])
    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df["date"], format="%Y%m%d")
    df["totalUsers"] = pd.to_numeric(df["totalUsers"], errors="coerce").fillna(0).astype(int)
    df = df[(df["date"] >= pd.Timestamp(start)) & (df["date"] <= pd.Timestamp(end))]
    return df.sort_values("date").reset_index(drop=True)

@st.cache_data(ttl=CACHE_TTL_MAIN, max_entries=CACHE_MAX_ENTRIES, show_spinner=False)
def fetch_mainsite_daily_ga4(start, end, organic_only=True):
    from config import SECTIONS
    total = fetch_daily_traffic(start, end, organic_only)
    if total.empty: return total
    result = total[["date","totalUsers"]].copy()
    for sec in SECTIONS:
        sec_df = fetch_section_daily_ga4(start, end, sec["prefix"], organic_only)
        if not sec_df.empty:
            merged = result.merge(sec_df[["date","totalUsers"]], on="date", how="left", suffixes=("","_sec"))
            result["totalUsers"] = merged["totalUsers"] - merged["totalUsers_sec"].fillna(0)
    result["totalUsers"] = result["totalUsers"].clip(lower=0).astype(int)
    return result

# ── Dedup-safe totals: "Total users" cannot be summed across days ──
# GA4's totalUsers is a unique-user count. Summing per-day values double-counts
# anyone who returns on more than one day. These two functions ask GA4 itself
# for the true deduplicated count over a range, instead of summing daily rows.

@st.cache_data(ttl=CACHE_TTL_MAIN, max_entries=CACHE_MAX_ENTRIES, show_spinner=False)
def fetch_users_total_ga4(start, end, organic_only=True):
    """True deduplicated total users for the whole [start, end] range, in one number.
    Uses a dimensionless query so GA4 computes the dedup itself (matches what
    GA4 Explore shows for the same date range and filter)."""
    filt = _organic_filter() if organic_only else None
    rows = _run([], ["totalUsers"], start, end, filt)
    if not rows: return 0
    return int(rows[0].get("totalUsers", 0))

@st.cache_data(ttl=CACHE_TTL_MAIN, max_entries=CACHE_MAX_ENTRIES, show_spinner=False)
def fetch_monthly_traffic_ga4(start, end, organic_only=True):
    """True deduplicated users PER CALENDAR MONTH via GA4's yearMonth dimension.
    NOT a resample/sum of daily totals (which would double-count repeat
    visitors across days) — each row here is GA4's own monthly dedup count."""
    filt = _organic_filter() if organic_only else None
    rows = _run(["yearMonth"], ["totalUsers"], start, end, filt)
    if not rows: return pd.DataFrame(columns=["date", "totalUsers"])
    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df["yearMonth"], format="%Y%m")
    df["totalUsers"] = pd.to_numeric(df["totalUsers"], errors="coerce").fillna(0).astype(int)
    return df[["date", "totalUsers"]].sort_values("date").reset_index(drop=True)

# ── Tier 2: country ───────────────────────────────────────────────

@st.cache_data(ttl=CACHE_TTL_MAIN, max_entries=CACHE_MAX_ENTRIES, show_spinner=False)
def fetch_country_traffic(start, end, organic_only=True):
    filt = _organic_filter() if organic_only else None
    rows = _run(["country"], ["totalUsers","sessions"], start, end, filt)
    if not rows: return pd.DataFrame(columns=["country","totalUsers","sessions"])
    df = pd.DataFrame(rows)
    for c in ["totalUsers","sessions"]: df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0).astype(int)
    return df[df["country"] != "(not set)"].sort_values("totalUsers", ascending=False).reset_index(drop=True)

# ── Tier 3: single-page daily (on demand, ~180 rows) ─────────────

@st.cache_data(ttl=CACHE_TTL_QUERY, max_entries=10, show_spinner=False)
def fetch_page_daily_ga4(start, end, page_path, organic_only=True):
    norm = normalize_path(page_path)
    filters = [FilterExpression(filter=Filter(
        field_name="pagePath", string_filter=Filter.StringFilter(
            match_type=Filter.StringFilter.MatchType.EXACT, value=norm)))]
    if organic_only: filters.append(_organic_filter())
    filt = _and_filters(*filters) if len(filters) > 1 else filters[0]
    rows = _run(["date"], ["totalUsers","sessions","screenPageViews"], start, end, filt)
    if not rows: return pd.DataFrame(columns=["date","totalUsers","sessions","screenPageViews"])
    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df["date"], format="%Y%m%d")
    for c in ["totalUsers","sessions","screenPageViews"]: df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0).astype(int)
    return df.sort_values("date").reset_index(drop=True)
