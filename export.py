"""
Binaytara SEO Monitor — Export helpers
Single-sheet and multi-sheet Excel export.
"""
import io
import pandas as pd
from datetime import date


def make_filename(prefix, start, end):
    return f"binaytara_{prefix}_{start}_to_{end}.xlsx"


def to_excel_bytes(df, sheet_name="Data", meta_note=""):
    """Single DataFrame to Excel bytes."""
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="xlsxwriter") as w:
        df.to_excel(w, sheet_name=sheet_name, index=False, startrow=1)
        ws = w.sheets[sheet_name]
        ws.write(0, 0, meta_note)
    return buf.getvalue()


def multi_sheet_excel(sheets_dict, meta_note=""):
    """
    Export multiple DataFrames as one Excel file with multiple sheets.
    sheets_dict: {"Sheet Name": pd.DataFrame, ...}
    Returns bytes.
    """
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="xlsxwriter") as w:
        for name, df in sheets_dict.items():
            if df is None or df.empty:
                continue
            safe_name = name[:31]  # Excel sheet name limit
            df.to_excel(w, sheet_name=safe_name, index=False, startrow=1)
            ws = w.sheets[safe_name]
            ws.write(0, 0, meta_note)
            # Auto-width columns (safe for all dtypes and pandas versions)
            for i, col in enumerate(df.columns):
                try:
                    max_len = max(df[col].astype(str).apply(lambda x: len(str(x))).max(), len(str(col))) + 2
                except Exception:
                    max_len = len(str(col)) + 5
                ws.set_column(i, i, min(max_len, 50))
    return buf.getvalue()
