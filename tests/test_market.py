from __future__ import annotations

import sys
from types import SimpleNamespace

from crypto_holdings.market import fetch_market_prices


class FakeFastInfo(dict):
    @property
    def last_price(self):
        return self.get("lastPrice")


class FakeTicker:
    def __init__(self, ticker: str):
        self.ticker = ticker
        self.fast_info = FakeFastInfo(lastPrice=123.45, currency="EUR")


def test_market_price_uses_current_yfinance_fast_info_keys(monkeypatch) -> None:
    monkeypatch.setitem(sys.modules, "yfinance", SimpleNamespace(Ticker=FakeTicker))
    result = fetch_market_prices(["TEST"])

    assert result.loc[0, "price"] == 123.45
    assert result.loc[0, "currency"] == "EUR"
    assert result.loc[0, "error"] is None
