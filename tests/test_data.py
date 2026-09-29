from __future__ import annotations

from io import BytesIO

import pandas as pd

from crypto_holdings.data import load_transactions, parse_number


def test_parse_number_supports_german_and_english_formats() -> None:
    assert parse_number("1.234,56 €") == 1234.56
    assert parse_number("1,234.56") == 1234.56
    assert parse_number("0,125") == 0.125
    assert parse_number("(42,50)") == -42.5
    assert parse_number(12.5) == 12.5


def test_trade_republic_headers_and_value_proxy_are_detected() -> None:
    payload = (
        "Datum,Transaktionen,ISIN,Name,Total,**Gesamte Steuern,**&#x53;umme\n"
        '"2026-01-01T10:00:00","BUY","XF000DOT0011","Polkadot","-41.98","","-42.98"\n'
    ).encode("utf-8")

    result = load_transactions(BytesIO(payload))

    assert result.is_valid
    assert result.precision_mode == "value-proxy"
    assert result.frame.loc[0, "asset_name"] == "Polkadot"
    assert result.frame.loc[0, "total"] == -41.98
    assert result.frame.loc[0, "net_amount"] == -42.98
    assert any("Quantity" in warning for warning in result.warnings)


def test_exact_quantity_mode_with_german_quantity_header() -> None:
    payload = (
        "Datum,Transaktionen,ISIN,Name,Total,Stück\n"
        '"2025-01-01T10:00:00","BUY","XF000BTC0001","Bitcoin","-1000,00","0,125"\n'
        '"2025-06-01T10:00:00","SELL","XF000BTC0001","Bitcoin","500,00","0,025"\n'
    ).encode("utf-8")

    result = load_transactions(payload)

    assert result.is_valid
    assert result.precision_mode == "exact-quantity"
    assert result.frame["quantity"].tolist() == [0.125, 0.025]
    assert pd.api.types.is_datetime64_any_dtype(result.frame["date"])


def test_missing_required_columns_returns_actionable_error() -> None:
    result = load_transactions(b"foo,bar\n1,2\n")
    assert not result.is_valid
    assert "Missing required columns" in result.errors[0]
