from __future__ import annotations

import pandas as pd
import pytest

from crypto_holdings.config import classify_asset, color_for_asset
from crypto_holdings.data import load_transactions
from crypto_holdings.portfolio import analyze_portfolio, eligibility_date


def exact_payload() -> bytes:
    return (
        "Date,Transaction,ISIN,Name,Total,Quantity,Ticker,Asset Type\n"
        "2025-01-01T10:00:00,BUY,XF000BTC0001,Bitcoin,-1000,10,BTC-USD,Crypto\n"
        "2025-08-01T10:00:00,BUY,XF000BTC0001,Bitcoin,-750,5,BTC-USD,Crypto\n"
        "2026-03-01T10:00:00,SELL,XF000BTC0001,Bitcoin,1200,8,BTC-USD,Crypto\n"
        "2025-02-01T10:00:00,BUY,US88160R1014,Tesla,-600,3,TSLA,Stock\n"
        "2025-06-01T10:00:00,SELL,US88160R1014,Tesla,250,1,TSLA,Stock\n"
    ).encode("utf-8")


def test_fifo_partial_sale_preserves_oldest_remaining_lot() -> None:
    loaded = load_transactions(exact_payload())
    analysis = analyze_portfolio(loaded.frame, as_of=pd.Timestamp("2026-05-01T12:00:00"))

    bitcoin = analysis.positions.loc[analysis.positions["asset_name"] == "Bitcoin"].iloc[0]
    btc_lots = analysis.lots.loc[analysis.lots["asset_name"] == "Bitcoin"]

    assert bitcoin["position_size"] == pytest.approx(7.0)
    assert bitcoin["tax_free_units"] == pytest.approx(2.0)
    assert bitcoin["locked_units"] == pytest.approx(5.0)
    assert bitcoin["tax_free_pct"] == pytest.approx(200 / 7)
    assert btc_lots["remaining_units"].tolist() == pytest.approx([2.0, 5.0])
    btc_disposal = analysis.disposals.loc[analysis.disposals["asset_name"] == "Bitcoin"].iloc[0]
    assert btc_disposal["units"] == pytest.approx(8.0)


def test_one_year_plus_one_day_boundary() -> None:
    acquired = pd.Timestamp("2025-01-01T10:00:00")
    assert eligibility_date(acquired) == pd.Timestamp("2026-01-02T10:00:00")

    loaded = load_transactions(
        b"Date,Transaction,ISIN,Name,Total,Quantity\n"
        b"2025-01-01T10:00:00,BUY,XF000BTC0001,Bitcoin,-100,1\n"
    )
    before = analyze_portfolio(loaded.frame, as_of="2026-01-02T09:59:59")
    at_boundary = analyze_portfolio(loaded.frame, as_of="2026-01-02T10:00:00")

    assert before.crypto_status.iloc[0]["tax_free_pct"] == 0
    assert at_boundary.crypto_status.iloc[0]["tax_free_pct"] == 100


def test_unmatched_opening_inventory_is_reported_not_invented() -> None:
    loaded = load_transactions(
        b"Date,Transaction,ISIN,Name,Total,Quantity\n"
        b"2026-01-05T10:00:00,SELL,US0000000001,Legacy Holding,500,2\n"
        b"2026-02-05T10:00:00,BUY,US0000000001,Legacy Holding,-100,1\n"
    )
    analysis = analyze_portfolio(loaded.frame, as_of="2026-03-01")

    assert len(analysis.issues) == 1
    assert analysis.issues.iloc[0]["units"] == pytest.approx(2.0)
    assert analysis.positions.iloc[0]["position_size"] == pytest.approx(1.0)
    assert "incomplete history" in analysis.positions.iloc[0]["status"]


def test_value_proxy_mode_is_explicit_per_position() -> None:
    loaded = load_transactions(
        b"Date,Transaction,ISIN,Name,Total\n"
        b"2026-01-01,BUY,XF000DOT0011,Polkadot,-100\n"
        b"2026-02-01,SELL,XF000DOT0011,Polkadot,40\n"
    )
    analysis = analyze_portfolio(loaded.frame, as_of="2026-03-01")
    position = analysis.positions.iloc[0]

    assert position["precision"] == "Value proxy"
    assert position["unit_kind"] == "€ proxy"
    assert position["position_size"] == pytest.approx(60.0)


def test_classification_and_color_are_deterministic() -> None:
    assert classify_asset("Polkadot", "XF000DOT0011") == "Crypto"
    assert classify_asset("Core S&P 500 USD (Acc)", "IE00B5BMR087") == "ETF"
    assert classify_asset("Short 180 $", "DE000ABC1234") == "Derivative"
    assert classify_asset("Tesla", "US88160R1014") == "Stock"
    assert color_for_asset("Tesla", "US88160R1014") == color_for_asset("Tesla", "US88160R1014")
