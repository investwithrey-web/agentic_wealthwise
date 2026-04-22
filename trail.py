# import requests
# import pandas as pd

# url = "https://www.amfiindia.com/spages/NAVAll.txt"
# res = requests.get(url)

# lines = res.text.split("\n")

# data = []
# for line in lines:
#     if ";" in line:
#         data.append(line.split(";"))

# df = pd.DataFrame(data, columns=[
#     "Scheme Code", "ISIN Div", "ISIN Growth",
#     "Scheme Name", "NAV", "Date"
# ])

# print(df.head())

# output_file = "amfi_nav_data.xlsx"
# df.to_excel(output_file, index=False)
# print(f"Saved data to {output_file}")



"""
============================================================
  Indian Mutual Fund Data Fetcher
  Sources: mfapi.in + mfdata.in
  No API key required — completely free
============================================================
"""

import requests
import time
import json
from datetime import datetime

BASE_MFAPI  = "https://api.mfapi.in/mf"
BASE_MFDATA = "https://api.mfdata.in/schemes"

# ─────────────────────────────────────────────
# 1. LIST / SEARCH SCHEMES
# ─────────────────────────────────────────────

def get_all_schemes():
    """Fetch the master list of all mutual fund schemes (~15,000+ schemes)."""
    print("Fetching all schemes from mfapi.in ...")
    r = requests.get(BASE_MFAPI, timeout=15)
    r.raise_for_status()
    schemes = r.json()
    print(f"  Total schemes found: {len(schemes)}")
    return schemes  # [{schemeCode, schemeName}, ...]


def search_schemes(keyword, schemes=None):
    """
    Search schemes by keyword (case-insensitive).
    Pass pre-loaded `schemes` list to avoid re-fetching.
    """
    if schemes is None:
        schemes = get_all_schemes()
    kw = keyword.lower()
    results = [s for s in schemes if kw in s["schemeName"].lower()]
    print(f"  Found {len(results)} schemes matching '{keyword}'")
    return results


# ─────────────────────────────────────────────
# 2. NAV DATA  (mfapi.in)
# ─────────────────────────────────────────────

def get_latest_nav(scheme_code):
    """Get only the latest NAV for a scheme."""
    r = requests.get(f"{BASE_MFAPI}/{scheme_code}/latest", timeout=10)
    r.raise_for_status()
    return r.json()  # {data: [{date, nav}], meta: {...}}


def get_historical_nav(scheme_code, days=30):
    """
    Get historical NAV data.
    Returns full fund info including metadata + up to `days` NAV records.
    """
    r = requests.get(f"{BASE_MFAPI}/{scheme_code}", timeout=15)
    r.raise_for_status()
    data = r.json()
    data["data"] = data.get("data", [])[:days]
    return data


# ─────────────────────────────────────────────
# 3. ANALYTICS (mfdata.in)
# ─────────────────────────────────────────────

def get_fund_analytics(scheme_code):
    """
    Get expense ratio, fund manager, AUM, Sharpe ratio, Beta, etc.
    from mfdata.in.
    Returns None if data not available for that scheme.
    """
    try:
        r = requests.get(f"{BASE_MFDATA}/{scheme_code}", timeout=10)
        if r.status_code == 404:
            return None
        r.raise_for_status()
        return r.json()
    except Exception:
        return None


# ─────────────────────────────────────────────
# 4. COMBINED FULL DETAILS
# ─────────────────────────────────────────────

def get_full_fund_info(scheme_code, history_days=10):
    """
    Fetch ALL available data for a scheme:
      - Metadata (name, house, category, type)
      - Latest NAV + daily change
      - Historical NAV
      - Expense ratio, fund manager, AUM, risk ratios
    """
    print(f"\nFetching full info for scheme code: {scheme_code}")

    # --- mfapi.in ---
    nav_data   = get_historical_nav(scheme_code, days=history_days)
    meta       = nav_data.get("meta", {})
    nav_list   = nav_data.get("data", [])

    # Compute 1-day NAV change
    nav_change_pct = None
    nav_change_abs = None
    if len(nav_list) >= 2:
        curr = float(nav_list[0]["nav"])
        prev = float(nav_list[1]["nav"])
        nav_change_abs = round(curr - prev, 4)
        nav_change_pct = round((curr - prev) / prev * 100, 4)

    # --- mfdata.in ---
    analytics = get_fund_analytics(scheme_code)

    # --- Combine ---
    result = {
        # Identification
        "scheme_code"     : meta.get("scheme_code", scheme_code),
        "scheme_name"     : meta.get("scheme_name", ""),
        "fund_house"      : meta.get("fund_house", ""),
        "scheme_type"     : meta.get("scheme_type", ""),
        "scheme_category" : meta.get("scheme_category", ""),

        # Latest NAV
        "latest_nav"      : float(nav_list[0]["nav"]) if nav_list else None,
        "nav_date"        : nav_list[0]["date"] if nav_list else None,
        "nav_change_abs"  : nav_change_abs,
        "nav_change_pct"  : nav_change_pct,

        # Historical NAV list
        "historical_nav"  : [
            {
                "date": entry["date"],
                "nav" : float(entry["nav"])
            }
            for entry in nav_list
        ],

        # Analytics (may be None if not available)
        "expense_ratio"   : analytics.get("expense_ratio")   if analytics else None,
        "fund_manager"    : analytics.get("fund_manager")     if analytics else None,
        "aum_cr"          : analytics.get("aum")              if analytics else None,
        "sharpe_ratio"    : analytics.get("sharpe_ratio")     if analytics else None,
        "beta"            : analytics.get("beta")             if analytics else None,
        "alpha"           : analytics.get("alpha")            if analytics else None,
        "std_deviation"   : analytics.get("std_deviation")   if analytics else None,
        "sortino_ratio"   : analytics.get("sortino_ratio")   if analytics else None,
    }

    return result


# ─────────────────────────────────────────────
# 5. PRETTY PRINT
# ─────────────────────────────────────────────

def print_fund_info(info):
    """Pretty-print the combined fund information."""
    sep = "─" * 52
    print(f"\n{sep}")
    print(f"  {info['scheme_name']}")
    print(sep)
    print(f"  Scheme Code  : {info['scheme_code']}")
    print(f"  Fund House   : {info['fund_house']}")
    print(f"  Category     : {info['scheme_category']}")
    print(f"  Type         : {info['scheme_type']}")

    print(f"\n  ── NAV ──")
    print(f"  Latest NAV   : ₹{info['latest_nav']} (as of {info['nav_date']})")
    chg = info['nav_change_pct']
    chg_abs = info['nav_change_abs']
    if chg is not None:
        arrow = "▲" if chg >= 0 else "▼"
        print(f"  1-Day Change : {arrow} ₹{chg_abs}  ({'+' if chg >= 0 else ''}{chg}%)")

    print(f"\n  ── Analytics ──")
    print(f"  Fund Manager : {info['fund_manager'] or 'N/A'}")
    print(f"  Expense Ratio: {str(info['expense_ratio']) + '%' if info['expense_ratio'] else 'N/A'}")
    print(f"  AUM          : {'₹' + str(info['aum_cr']) + ' Cr' if info['aum_cr'] else 'N/A'}")
    print(f"  Sharpe Ratio : {info['sharpe_ratio'] or 'N/A'}")
    print(f"  Beta         : {info['beta'] or 'N/A'}")
    print(f"  Alpha        : {info['alpha'] or 'N/A'}")
    print(f"  Std Deviation: {info['std_deviation'] or 'N/A'}")
    print(f"  Sortino Ratio: {info['sortino_ratio'] or 'N/A'}")

    print(f"\n  ── Historical NAV (last {len(info['historical_nav'])} days) ──")
    hist = info["historical_nav"]
    for i, entry in enumerate(hist):
        if i + 1 < len(hist):
            prev_nav = hist[i + 1]["nav"]
            chg_d = round(((entry["nav"] - prev_nav) / prev_nav) * 100, 3)
            arrow = "▲" if chg_d >= 0 else "▼"
            print(f"  {entry['date']}  ₹{entry['nav']:<10}  {arrow} {chg_d:+.3f}%")
        else:
            print(f"  {entry['date']}  ₹{entry['nav']}")
    print(sep)


# ─────────────────────────────────────────────
# 6. BULK FETCH (multiple funds)
# ─────────────────────────────────────────────

def get_multiple_funds(scheme_codes, history_days=5, delay=0.5):
    """
    Fetch full info for a list of scheme codes.
    `delay` in seconds between requests to be polite to the API.
    Returns a list of fund info dicts.
    """
    results = []
    for code in scheme_codes:
        info = get_full_fund_info(code, history_days=history_days)
        results.append(info)
        time.sleep(delay)
    return results


# ─────────────────────────────────────────────
# 7. EXPORT TO JSON / CSV
# ─────────────────────────────────────────────

def export_to_json(funds, filename="mutual_funds_data.json"):
    """Save fund data list to a JSON file."""
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(funds, f, indent=2, ensure_ascii=False)
    print(f"\nExported {len(funds)} fund(s) to {filename}")


def export_to_csv(funds, filename="mutual_funds_data.csv"):
    """Save fund summary (excluding historical NAV) to a CSV file."""
    import csv
    fields = [
        "scheme_code", "scheme_name", "fund_house", "scheme_type",
        "scheme_category", "latest_nav", "nav_date", "nav_change_abs",
        "nav_change_pct", "expense_ratio", "fund_manager", "aum_cr",
        "sharpe_ratio", "beta", "alpha", "std_deviation", "sortino_ratio",
    ]
    with open(filename, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(funds)
    print(f"Exported {len(funds)} fund(s) to {filename}")


# ─────────────────────────────────────────────
# MAIN — DEMO
# ─────────────────────────────────────────────

if __name__ == "__main__":

    # ── Example 1: Search by name ──────────────────────────────
    print("\n═══ EXAMPLE 1: Search by name ═══")
    all_schemes = get_all_schemes()
    sbi_funds = search_schemes("SBI Bluechip", schemes=all_schemes)
    for f in sbi_funds[:5]:
        print(f"  {f['schemeCode']}  {f['schemeName']}")

    # ── Example 2: Full details for one fund ───────────────────
    print("\n═══ EXAMPLE 2: Full details for one fund ═══")
    # HDFC Mid-Cap Opportunities Fund — Direct Growth
    fund_info = get_full_fund_info(scheme_code=118989, history_days=10)
    print_fund_info(fund_info)

    # ── Example 3: Multiple funds at once ─────────────────────
    print("\n═══ EXAMPLE 3: Multiple funds ═══")
    codes = [
        118989,   # HDFC Mid-Cap Opportunities
        120503,   # Mirae Asset Large Cap
        119597,   # Axis Bluechip
        100122,   # SBI Magnum Gilt
    ]
    all_funds = get_multiple_funds(codes, history_days=5, delay=0.5)
    for f in all_funds:
        print(f"  [{f['scheme_code']}] {f['scheme_name']}")
        print(f"    NAV: ₹{f['latest_nav']} | Change: {f['nav_change_pct']}% | "
              f"Expense: {f['expense_ratio'] or 'N/A'}% | Manager: {f['fund_manager'] or 'N/A'}")

    # ── Example 4: Export ──────────────────────────────────────
    print("\n═══ EXAMPLE 4: Export ═══")
    export_to_json(all_funds, "mutual_funds_data.json")
    export_to_csv(all_funds,  "mutual_funds_data.csv")

    print("\nDone!")