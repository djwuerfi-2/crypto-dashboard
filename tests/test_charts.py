from __future__ import annotations

import pandas as pd

from crypto_holdings.charts import build_position_timeline, build_tax_free_donut
from crypto_holdings.data import load_transactions
from crypto_holdings.portfolio import analyze_portfolio


def _analysis():
    loaded = load_transactions(
        b"Date,Transaction,ISIN,Name,Total,Quantity,Asset Type\n"
        b"2026-01-01,BUY,XF000DOT0011,Polkadot,-100,10,Crypto\n"
        b"2026-02-01,BUY,US88160R1014,Tesla,-200,1,Stock\n"
    )
    return analyze_portfolio(loaded.frame, as_of="2026-06-01")


def test_timeline_contains_today_marker_and_projection() -> None:
    analysis = _analysis()
    figure = build_position_timeline(analysis.positions, analysis.as_of)
    payload = figure.to_plotly_json()

    assert len(payload["data"]) >= 3
    assert payload["layout"]["height"] == 560
    assert payload["layout"]["xaxis"]["rangeslider"]["visible"] is True
    assert payload["layout"]["xaxis"]["range"][0] == pd.Timestamp("2026-03-01")


def test_donut_uses_real_free_and_locked_values() -> None:
    analysis = _analysis()
    row = analysis.crypto_status.iloc[0].copy()
    row["tax_free_units"] = 4.0
    row["locked_units"] = 6.0
    row["total_units"] = 10.0
    row["tax_free_pct"] = 40.0
    figure = build_tax_free_donut(row)
    assert list(figure.data[0]["values"]) == [4.0, 6.0]
