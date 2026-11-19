# Binaytara SEO Monitor (v3)

Interactive GA4 + Google Search Console organic-traffic monitor for binaytara.org.
Real data only: GSC clicks/impressions/CTR/position and GA4 organic users.

## v3: lightweight architecture for Streamlit free plan

### What changed from v2
v2 crashed after 2-3 filter changes because two data fetchers pulled 1M+ and 4.5M+ rows,
exceeding the free plan's 1 GB RAM. v3 fixes this with a tiered loading architecture:

**Tier 1 (always loaded, tiny):** Daily site totals from GA4 + GSC (~360 rows total).
Powers the hero chart, exact trend, and scorecards.

**Tier 2 (per-tab, moderate):** Page summaries (~6K rows each), section daily data
(5 small API calls per source, ~180 rows each instead of 1M+), country and device data.
Loaded when the tab opens, cached with max_entries=5.

**Tier 3 (on demand, one click):** Per-page daily trend, per-page query drill-down,
position-bucket trend (limited to 60 days max). Loaded only when you explicitly ask.

**Result:** Initial load drops from ~35 API calls / ~1.4 GB to ~8 calls / ~19 MB.
Filter changes stay within 39 MB worst case. No more crashes.

### New features
- **Decline drill-down:** When traffic drops, select a declining page and see which
  specific queries lost clicks, with position changes. One API call per page, on demand.
- **Per-page daily trend:** Select any page on the Pages tab to load its day-by-day
  traffic from GA4 and GSC, with inline query view.
- **Section over time with GSC clicks:** Both GA4 users (solid lines) and GSC clicks
  (dotted lines) per section, each fetched via an API-level page filter (~180 rows per
  section instead of 1,080,000).
- **Traffic overlay:** Check both "Organic Traffic" and "Total Traffic" to see both
  lines on the same chart.
- **Month-to-date pace card:** Lazy-loaded (collapsed by default, loads on expand).
  Shows this month vs same days last month, projected month-end, and last month actual.
- **SSL retry:** All API calls retry up to 3 times on transient SSL errors.

### Deploy
1. Service account with GA4 Viewer (468739074) and GSC Full (sc-domain:binaytara.org).
2. Push to GitHub, deploy on Streamlit Community Cloud, main file: `app.py`.
3. Advanced settings → Secrets → paste service-account JSON as `[gcp_service_account]`.
