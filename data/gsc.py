"""
Binaytara SEO Monitor v3 — GSC Data Fetcher
Lightweight: section daily via API page filter. No bulk date×query.
"""
import streamlit as st
import pandas as pd
from auth import gsc_service
from config import (GSC_SITE_URL, GSC_ROW_LIMIT, GSC_QUERY_ROW_LIMIT,
                    CACHE_TTL_MAIN, CACHE_TTL_QUERY, CACHE_MAX_ENTRIES)
from utils import retry_on_ssl

@retry_on_ssl(max_retries=3, delay=2.0)
def _query(body):
    svc = gsc_service()
    return svc.searchanalytics().query(siteUrl=GSC_SITE_URL, body=body).execute().get("rows", [])

def _paginate(dimensions, start, end, row_limit, extra=None):
    all_rows, start_row = [], 0
    while True:
        body = {"startDate": start, "endDate": end, "dimensions": dimensions,
                "rowLimit": row_limit, "startRow": start_row}
        if extra: body.update(extra)
        rows = _query(body)
        if not rows: break
        all_rows.extend(rows)
        if len(rows) < row_limit: break
        start_row += row_limit
    return all_rows

# ── Tier 1: daily site totals (~180 rows) ─────────────────────────

@st.cache_data(ttl=CACHE_TTL_MAIN, max_entries=CACHE_MAX_ENTRIES, show_spinner=False)
def fetch_gsc_daily_totals(start, end):
    rows = _paginate(["date"], start, end, GSC_ROW_LIMIT)
    if not rows: return pd.DataFrame(columns=["date","clicks","impressions","ctr","position"])
    df = pd.DataFrame([{"date":r["keys"][0],"clicks":r["clicks"],"impressions":r["impressions"],
                        "ctr":r["ctr"],"position":r["position"]} for r in rows])
    df["date"] = pd.to_datetime(df["date"])
    df = df[(df["date"] >= pd.Timestamp(start)) & (df["date"] <= pd.Timestamp(end))]
    return df.sort_values("date").reset_index(drop=True)

# ── Tier 2: page summary (~6K rows) ──────────────────────────────

@st.cache_data(ttl=CACHE_TTL_MAIN, max_entries=CACHE_MAX_ENTRIES, show_spinner=False)
def fetch_gsc_page_summary(start, end):
    rows = _paginate(["page"], start, end, GSC_ROW_LIMIT)
    if not rows: return pd.DataFrame(columns=["page","gsc_clicks","gsc_impressions","gsc_ctr","gsc_position"])
    df = pd.DataFrame([{"page":r["keys"][0],"gsc_clicks":r["clicks"],"gsc_impressions":r["impressions"],
                        "gsc_ctr":r["ctr"],"gsc_position":r["position"]} for r in rows])
    return df[df["page"].str.contains("binaytara.org", na=False)].copy()

# ── Tier 2: section daily GSC (LIGHTWEIGHT: ~180 rows per section) ──

@st.cache_data(ttl=CACHE_TTL_MAIN, max_entries=20, show_spinner=False)
def fetch_section_daily_gsc(start, end, section_url_pattern):
    """Daily clicks/impressions for ONE section via page-contains filter."""
    extra = {"dimensionFilterGroups": [{"filters": [
        {"dimension": "page", "operator": "contains", "expression": section_url_pattern}]}]}
    rows = _paginate(["date"], start, end, GSC_ROW_LIMIT, extra)
    if not rows: return pd.DataFrame(columns=["date","clicks","impressions","ctr","position"])
    df = pd.DataFrame([{"date":r["keys"][0],"clicks":r["clicks"],"impressions":r["impressions"],
                        "ctr":r["ctr"],"position":r["position"]} for r in rows])
    df["date"] = pd.to_datetime(df["date"])
    df = df[(df["date"] >= pd.Timestamp(start)) & (df["date"] <= pd.Timestamp(end))]
    return df.sort_values("date").reset_index(drop=True)

# ── Tier 2: query totals (site-wide, ~25K rows) ──────────────────

@st.cache_data(ttl=CACHE_TTL_QUERY, max_entries=CACHE_MAX_ENTRIES, show_spinner=False)
def fetch_gsc_query_totals(start, end):
    rows = _paginate(["query"], start, end, GSC_QUERY_ROW_LIMIT)
    if not rows: return pd.DataFrame(columns=["query","clicks","impressions","ctr","position"])
    return pd.DataFrame([{"query":r["keys"][0],"clicks":r["clicks"],"impressions":r["impressions"],
                          "ctr":r["ctr"],"position":r["position"]} for r in rows])

@st.cache_data(ttl=CACHE_TTL_MAIN, max_entries=CACHE_MAX_ENTRIES, show_spinner=False)
def fetch_gsc_device_totals(start, end):
    rows = _paginate(["device"], start, end, 100)
    if not rows: return pd.DataFrame(columns=["device","clicks","impressions","ctr","position"])
    return pd.DataFrame([{"device":r["keys"][0].title(),"clicks":r["clicks"],"impressions":r["impressions"],
                          "ctr":r["ctr"],"position":r["position"]} for r in rows])

# ── Tier 3: on-demand page queries (~100-500 rows per page) ──────

@st.cache_data(ttl=CACHE_TTL_QUERY, max_entries=10, show_spinner=False)
def fetch_gsc_queries_for_page(page_url, start, end):
    extra = {"dimensionFilterGroups": [{"filters": [
        {"dimension": "page", "expression": page_url, "operator": "equals"}]}]}
    rows = _paginate(["page","query"], start, end, GSC_QUERY_ROW_LIMIT, extra)
    if not rows: return pd.DataFrame(columns=["query","clicks","impressions","ctr","position"])
    return pd.DataFrame([{"query":r["keys"][1],"clicks":r["clicks"],"impressions":r["impressions"],
                          "ctr":r["ctr"],"position":round(r["position"],1)} for r in rows])

# ── Tier 3: on-demand page daily GSC (~180 rows) ─────────────────

@st.cache_data(ttl=CACHE_TTL_QUERY, max_entries=10, show_spinner=False)
def fetch_page_daily_gsc(page_url, start, end):
    """Daily clicks/impressions for ONE page. On-demand only."""
    extra = {"dimensionFilterGroups": [{"filters": [
        {"dimension": "page", "expression": page_url, "operator": "equals"}]}]}
    rows = _paginate(["date","page"], start, end, GSC_ROW_LIMIT, extra)
    if not rows: return pd.DataFrame(columns=["date","clicks","impressions","ctr","position"])
    df = pd.DataFrame([{"date":r["keys"][0],"clicks":r["clicks"],"impressions":r["impressions"],
                        "ctr":r["ctr"],"position":r["position"]} for r in rows])
    df["date"] = pd.to_datetime(df["date"])
    return df.sort_values("date").reset_index(drop=True)

# ── Tier 3: position bucket (limited, behind button) ─────────────

@st.cache_data(ttl=CACHE_TTL_QUERY, max_entries=3, show_spinner=False)
def fetch_gsc_date_query_limited(start, end):
    """Date×query but ONLY for short ranges (max 60 days enforced by caller)."""
    rows = _paginate(["date","query"], start, end, GSC_QUERY_ROW_LIMIT)
    if not rows: return pd.DataFrame(columns=["date","query","clicks","impressions","ctr","position"])
    df = pd.DataFrame([{"date":r["keys"][0],"query":r["keys"][1],"clicks":r["clicks"],
                        "impressions":r["impressions"],"ctr":r["ctr"],"position":r["position"]} for r in rows])
    df["date"] = pd.to_datetime(df["date"])
    return df

# ── Compare queries for a page (New/Lost/Retained) ───────────────

def compare_queries(page_url, cs, ce, ps, pe):
    curr = fetch_gsc_queries_for_page(page_url, cs, ce)
    prev = fetch_gsc_queries_for_page(page_url, ps, pe)
    cm = {r["query"]: r.to_dict() for _, r in curr.iterrows()} if not curr.empty else {}
    pm = {r["query"]: r.to_dict() for _, r in prev.iterrows()} if not prev.empty else {}
    result = []
    for q in set(cm)|set(pm):
        c, p = cm.get(q), pm.get(q)
        status = "New" if p is None else ("Lost" if c is None else "Retained")
        cc, pc = (c["clicks"] if c else 0), (p["clicks"] if p else 0)
        ci, pi = (c["impressions"] if c else 0), (p["impressions"] if p else 0)
        cp_, pp_ = (c["position"] if c else None), (p["position"] if p else None)
        pd_ = round(cp_-pp_,1) if (cp_ is not None and pp_ is not None) else None
        result.append({"query":q,"status":status,"clicks_curr":cc,"clicks_prev":pc,
                       "clicks_change":cc-pc,"impr_curr":ci,"impr_prev":pi,"impr_change":ci-pi,
                       "pos_curr":cp_,"pos_prev":pp_,"pos_change":pd_})
    if not result: return pd.DataFrame()
    df = pd.DataFrame(result)
    so = {"Lost":0,"Retained":1,"New":2}
    df["_s"] = df["status"].map(so)
    return df.sort_values(["_s","clicks_change"], ascending=[True,True]).drop(columns=["_s"]).reset_index(drop=True)
