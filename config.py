"""
Binaytara SEO Monitor v3 — Configuration
"""

GA4_PROPERTY_ID = "468739074"
GSC_SITE_URL = "sc-domain:binaytara.org"
SITE_DOMAIN = "https://binaytara.org"

# Section definitions (order matters; first match wins)
SECTIONS = [
    {"name": "TCN",         "prefix": "/cancernews",           "gsc_pattern": "binaytara.org/cancernews"},
    {"name": "Journal",     "prefix": "/journal",              "gsc_pattern": "binaytara.org/journal"},
    {"name": "Conferences", "prefix": "/projects/conferences", "gsc_pattern": "binaytara.org/projects/conferences"},
    {"name": "OncoBlast",   "prefix": "/projects/oncoblast",   "gsc_pattern": "binaytara.org/projects/oncoblast"},
]
DEFAULT_SECTION = "Main Site"

SECTION_COLORS = {
    "TCN": "#1B3A6B", "Journal": "#2E8B57", "Conferences": "#C77C2E",
    "OncoBlast": "#7E4E9B", "Main Site": "#5F6B7A",
}

BRANDED_TERMS = ["binaytara", "binay tara", "the cancer news", "oncoblast", "ijccd", "binaytara foundation"]

DATA_LAG_DAYS = 3
DEFAULT_PRESET = "Last 3 months"
DATE_PRESETS = {"Last 7 days": 7, "Last 28 days": 28, "Last 3 months": 90,
                "Last 6 months": 180, "Last 12 months": 365, "Custom": None}
ROLLING_WINDOW_DAYS = 28
GRANULARITY_OPTIONS = ["Daily", "Weekly", "Monthly"]
SMOOTHING_OPTIONS = ["Raw", "7-day average", "28-day average"]

# Cache: TTL + max_entries caps memory on the free plan (1 GB)
CACHE_TTL_MAIN = 3600
CACHE_TTL_QUERY = 1800
CACHE_MAX_ENTRIES = 5  # per function; prevents filter-change memory buildup

GA4_ROW_LIMIT = 100_000
GSC_ROW_LIMIT = 25_000
GSC_QUERY_ROW_LIMIT = 25_000

# Striking distance
STRIKING_BAND_PRESETS = {
    "11–20 (page 2, standard)": (11, 20), "8–20 (bottom of page 1 + page 2)": (8, 20),
    "5–20 (wide)": (5, 20), "4–15 (AI-era)": (4, 15),
}
STRIKING_MIN_IMPRESSIONS = 50
CTR_OPP_MIN_IMPRESSIONS = 100
CTR_OPP_MAX_CTR = 0.02
POSITION_BUCKETS = [("1–3 (Top 3)", 1, 3), ("4–10 (Page 1)", 4, 10),
                    ("11–20 (Page 2)", 11, 20), ("21–50", 21, 50), ("51+", 51, 1000)]

DECLINE_MIN_CHANGE_PCT = -0.15
DECLINE_MIN_PREV_USERS = 20
GROWTH_MIN_CHANGE_PCT = 0.25
GROWTH_MIN_CURR_USERS = 30

BRAND_NAVY = "#1B3A6B"; BRAND_GREEN = "#1E7E34"; BRAND_RED = "#DC3545"; BRAND_GRAY = "#5F6B7A"; BRAND_LIGHT_BLUE = "#E8F0FE"
