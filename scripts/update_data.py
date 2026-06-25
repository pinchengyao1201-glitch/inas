#!/usr/bin/env python3
"""
Refresh the live data points in index.html (then mirror to inas.html).

Macro indicators come from FRED's keyless CSV endpoint and ALWAYS update.
Microsoft fundamentals update only if a provider API key is present in the
environment (FMP_API_KEY preferred, else FINNHUB_API_KEY); otherwise the
existing snapshot values are left untouched.

Targets are HTML elements carrying a data-live="KEY" attribute. The script
replaces only the text inside those elements, so the page markup/styling is
never disturbed.

No third-party packages — standard library only.
"""

import json
import os
import re
import sys
import urllib.request
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
INDEX = os.path.join(HERE, "..", "index.html")
MIRROR = os.path.join(HERE, "..", "inas.html")
UA = "Mozilla/5.0 (inas-live-data-bot)"


def _get(url, timeout=25):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8")


def fred_latest(series_id, transformation=None):
    """Return the most recent numeric value of a FRED series (keyless CSV)."""
    url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}"
    if transformation:
        url += f"&transformation={transformation}"
    last = None
    for line in _get(url).splitlines()[1:]:
        parts = line.split(",")
        if len(parts) == 2 and parts[1] not in (".", ""):
            try:
                last = float(parts[1])
            except ValueError:
                continue
    return last


def collect_macro():
    """All four macro indicators from FRED. Returns {key: formatted_string}."""
    out = {}
    try:
        lo = fred_latest("DFEDTARL")
        hi = fred_latest("DFEDTARU")
        if lo is not None and hi is not None:
            out["fed-funds"] = f"{lo:.2f}–{hi:.2f}%"
    except Exception as e:
        print(f"  ! fed-funds: {e}")
    for key, series, tf, fmt in [
        ("t10y", "DGS10", None, "{:.2f}%"),
        ("cpi", "CPIAUCSL", "pc1", "{:.1f}%"),
        ("gdp", "A191RL1Q225SBEA", None, "{:+.1f}%"),
    ]:
        try:
            v = fred_latest(series, tf)
            if v is not None:
                out[key] = fmt.format(v)
        except Exception as e:
            print(f"  ! {key}: {e}")
    out["updated"] = date.today().isoformat()
    return out


def _pick(d, names):
    for n in names:
        v = d.get(n)
        if v not in (None, "", 0):
            try:
                return float(v)
            except (TypeError, ValueError):
                pass
    return None


def collect_msft():
    """Microsoft fundamentals. Returns {} if no key / fetch fails."""
    fmp = os.environ.get("FMP_API_KEY")
    finn = os.environ.get("FINNHUB_API_KEY")
    raw = {}  # normalized: pe, mktcap(USD), gross/op/net/roic/roa(percent), de(ratio)
    try:
        if fmp:
            r = json.loads(_get(
                f"https://financialmodelingprep.com/api/v3/ratios-ttm/MSFT?apikey={fmp}"))
            d = r[0] if isinstance(r, list) and r else {}
            raw["pe"] = _pick(d, ["peRatioTTM", "priceEarningsRatioTTM"])
            for k, names in {
                "gross": ["grossProfitMarginTTM"],
                "op": ["operatingProfitMarginTTM"],
                "net": ["netProfitMarginTTM", "netIncomePerTTM"],
                "roic": ["returnOnInvestedCapitalTTM", "returnOnCapitalEmployedTTM"],
                "roa": ["returnOnAssetsTTM"],
            }.items():
                v = _pick(d, names)
                if v is not None:
                    raw[k] = v * 100  # FMP margins are fractions
            raw["de"] = _pick(d, ["debtEquityRatioTTM", "debtToEquityTTM"])
            mc = json.loads(_get(
                f"https://financialmodelingprep.com/api/v3/market-capitalization/MSFT?apikey={fmp}"))
            if isinstance(mc, list) and mc:
                raw["mktcap"] = float(mc[0].get("marketCap"))
            print("  using FMP")
        elif finn:
            r = json.loads(_get(
                f"https://finnhub.io/api/v1/stock/metric?symbol=MSFT&metric=all&token={finn}"))
            m = r.get("metric", {})
            raw["pe"] = _pick(m, ["peTTM", "peInclExtraTTM"])
            mcap = _pick(m, ["marketCapitalization"])  # millions USD
            if mcap is not None:
                raw["mktcap"] = mcap * 1e6
            raw["gross"] = _pick(m, ["grossMarginTTM"])      # already percent
            raw["op"] = _pick(m, ["operatingMarginTTM"])
            raw["net"] = _pick(m, ["netProfitMarginTTM", "netMarginTTM"])
            raw["roic"] = _pick(m, ["roiTTM"])
            raw["roa"] = _pick(m, ["roaTTM"])
            raw["de"] = _pick(m, ["totalDebt/totalEquityQuarterly",
                                  "totalDebt/totalEquityAnnual",
                                  "longTermDebt/equityQuarterly"])
            print("  using Finnhub")
        else:
            print("  no stock API key set (FMP_API_KEY / FINNHUB_API_KEY) — "
                  "leaving Microsoft snapshot as-is")
            return {}
    except Exception as e:
        print(f"  ! stock fetch failed ({e}) — leaving snapshot as-is")
        return {}

    out = {}
    if raw.get("pe") is not None:
        out["pe"] = f"{raw['pe']:.1f}×"
    if raw.get("mktcap") is not None:
        out["mktcap"] = f"${raw['mktcap'] / 1e12:.1f}T"
    for k in ("gross", "op", "net", "roic", "roa"):
        if raw.get(k) is not None:
            out[k] = f"{raw[k]:.1f}%"
    if raw.get("de") is not None:
        out["de"] = f"{raw['de']:.2f}×"
    return out


def apply(html, values):
    """Replace inner text of each <... data-live="KEY" ...>OLD</...>."""
    changed = 0
    for key, val in values.items():
        pat = re.compile(r'(data-live="' + re.escape(key) + r'"[^>]*>)(.*?)(</)')
        new = pat.sub(lambda m: m.group(1) + val + m.group(3), html, count=1)
        if new != html:
            changed += 1
        html = new
    return html, changed


def main():
    with open(INDEX, encoding="utf-8") as f:
        html = f.read()

    print("Fetching macro (FRED, keyless)…")
    macro = collect_macro()
    for k, v in macro.items():
        print(f"  {k:10s} -> {v}")

    print("Fetching Microsoft fundamentals…")
    msft = collect_msft()
    for k, v in msft.items():
        print(f"  {k:10s} -> {v}")

    html, c1 = apply(html, macro)
    html, c2 = apply(html, msft)

    with open(INDEX, "w", encoding="utf-8") as f:
        f.write(html)
    with open(MIRROR, "w", encoding="utf-8") as f:
        f.write(html)  # keep inas.html identical to index.html

    print(f"Updated {c1 + c2} value(s). Wrote index.html and inas.html.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
