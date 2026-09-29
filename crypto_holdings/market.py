"""Optional, failure-tolerant Yahoo Finance price enrichment."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable

import pandas as pd


def fetch_market_prices(tickers: Iterable[str]) -> pd.DataFrame:
    """Fetch last prices one-by-one so one bad symbol cannot fail the portfolio."""

    import yfinance as yf

    records: list[dict[str, object]] = []
    for raw_ticker in sorted({str(value).strip().upper() for value in tickers if value}):
        record: dict[str, object] = {
            "ticker": raw_ticker,
            "price": None,
            "currency": None,
            "price_time": datetime.now(timezone.utc),
            "error": None,
        }
        try:
            info = yf.Ticker(raw_ticker).fast_info
            # yfinance exposes snake_case attributes but camelCase mapping keys.
            price = info.get("lastPrice") or getattr(info, "last_price", None)
            currency = info.get("currency")
            if price is None:
                raise ValueError("No last price returned")
            record["price"] = float(price)
            record["currency"] = str(currency or "")
        except Exception as exc:  # network/provider failures must stay non-blocking
            record["error"] = str(exc)[:160]
        records.append(record)
    return pd.DataFrame(records)
