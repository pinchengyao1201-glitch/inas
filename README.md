# INAS — Industry Network Analysis Framework

A single-page educational site (`index.html`) deployed via GitHub Pages:
**https://pinchengyao1201-glitch.github.io/inas/**

## Live data

Selected numbers on the page are refreshed automatically by a scheduled
GitHub Action (`.github/workflows/update-data.yml`) that runs
`scripts/update_data.py`. The script edits only the text inside elements
marked `data-live="…"`, so styling/markup is never touched. `inas.html` is
kept identical to `index.html`.

### Macro indicators — live out of the box (no key)

Pulled from FRED's keyless CSV endpoint:

| Page value      | FRED series        |
|-----------------|--------------------|
| Fed Funds Rate  | `DFEDTARL`/`DFEDTARU` |
| 10Y Treasury    | `DGS10`            |
| CPI Inflation   | `CPIAUCSL` (YoY)   |
| GDP Growth      | `A191RL1Q225SBEA`  |

### Microsoft fundamentals — opt-in (free API key)

The 8 Microsoft metrics (P/E, market cap, margins, ROIC, ROA, debt/equity)
update **only if** a stock API key is available. Without one, the existing
snapshot values are left in place.

To enable:
1. Get a free key from [Financial Modeling Prep](https://site.financialmodelingprep.com/developer/docs)
   (preferred) or [Finnhub](https://finnhub.io/).
2. In the repo: **Settings → Secrets and variables → Actions → New repository secret**.
3. Name it `FMP_API_KEY` (or `FINNHUB_API_KEY`) and paste the key.

The key lives only in GitHub Secrets — it is never exposed in the public page.

### Not auto-updatable

Cloud market share (AWS/Azure/GCP) and the S&P sector weight come from paid
analyst data with no free API; the portfolio allocation is an illustrative
example. These remain static by design.

## Run the updater manually

```bash
python3 scripts/update_data.py            # macro only
FMP_API_KEY=xxxx python3 scripts/update_data.py   # macro + Microsoft
```

Or trigger the workflow from the repo's **Actions** tab → *Update live data* → *Run workflow*.
