# Crypto Horizon

Crypto Horizon is a local-first Streamlit dashboard for visualizing security and crypto holding periods. It reconstructs purchases and sales with FIFO, highlights the German one-year crypto horizon, and makes data gaps visible instead of silently guessing.

## What it does

- Uploads Trade Republic-style tax CSVs and common transaction CSV variants.
- Shows a fixed-height, pannable portfolio timeline centered on today (three months back and forward initially).
- Uses solid bars for recorded holding history and faded crypto bars for the projected maturity period.
- Supports click-to-drill-down into individual purchase lots and their matched sales.
- Sorts by position size ascending/descending or alphabetically.
- Filters Crypto, Stock, ETF, Derivative, and Other instruments independently.
- Calculates the currently tax-free percentage of every active crypto position.
- Lists crypto lots unlocking in the next 30/90 days.
- Exports the calculated position view as CSV.
- Optionally loads indicative Yahoo Finance prices when a ticker is available.

## Run locally

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
streamlit run app.py
```

Then open `http://localhost:8501` if Streamlit does not open the browser automatically.

To run the test suite:

```powershell
python -m pip install -r requirements-dev.txt
pytest -q
```

## CSV schema

Minimum supported columns:

| Meaning | Common column names |
| --- | --- |
| Date/time | `Datum`, `Date`, `Timestamp` |
| Transaction type | `Transaktionen`, `Transaction`, `Type` |
| Instrument | `Name`, `Asset`, `Instrument` |
| Trade value | `Total`, `Betrag`, `Summe` |

Recommended for exact results:

| Optional column | Purpose |
| --- | --- |
| `Quantity` / `Stück` | Enables exact FIFO quantities and exact tax-free percentages |
| `ISIN` | Keeps instruments with similar names separate |
| `Ticker` | Enables optional current market prices |
| `Asset Type` | Overrides automatic classification (`Crypto`, `Stock`, `ETF`, `Derivative`) |

The included [`sample_data/demo_transactions.csv`](sample_data/demo_transactions.csv) demonstrates the complete schema.

## Important accuracy boundary

The Trade Republic **tax overview** export shown in the project brief contains cash values but no quantities. Cash values cannot reconstruct exact remaining coin/share counts after price changes. Crypto Horizon therefore has two modes:

- **Exact quantity** — all BUY/SELL rows for an asset contain Quantity/Stück. FIFO and tax-free shares are calculated in real units.
- **Value proxy** — quantity is missing. Absolute transaction values are treated as labelled proxy units. This produces a useful directional timeline, but it is not a tax-grade holdings calculation.

SELL rows whose purchase happened before the CSV window are reported as unmatched opening inventory. The application never invents the missing purchase date or quantity.

## Holding-period convention

For private crypto assets, the dashboard marks a remaining lot as eligible at the recorded acquisition timestamp plus one calendar year plus one safety day. This is a planning visualization based on [§ 23 EStG](https://www.gesetze-im-internet.de/estg/__23.html) and the [German Federal Ministry of Finance guidance dated 6 March 2025](https://www.bundesfinanzministerium.de/Content/DE/Downloads/BMF_Schreiben/Steuerarten/Einkommensteuer/2025-03-06-einzelfragen-kryptowerte.html).

This project is not tax advice. Transfers, staking, lending, token swaps, business assets, prior opening inventory, and instrument-specific classifications can change the result and require professional review.

## Market prices

Price loading is opt-in from the sidebar. A CSV-provided `Ticker` takes precedence over the small built-in convenience mapping. Prices are cached for 15 minutes, are purely indicative, and never affect FIFO or holding-period calculations. The dashboard remains fully usable if the provider or network is unavailable.

## Privacy

Uploaded CSV data is processed in the running Streamlit process. The app does not upload the portfolio to a database. Enabling current prices sends only mapped ticker symbols to Yahoo Finance through `yfinance`.
