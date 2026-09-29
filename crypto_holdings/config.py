"""Shared aliases, asset metadata, and visual constants."""

from __future__ import annotations

import hashlib
import re
import unicodedata


CRYPTO_NAMES = {
    "avalanche",
    "axie infinity",
    "bitcoin",
    "cardano",
    "chainlink",
    "dogecoin",
    "ethereum",
    "fetch.ai",
    "litecoin",
    "near protocol",
    "polkadot",
    "polygon",
    "render",
    "ripple",
    "shiba inu",
    "solana",
    "stellar",
    "sui",
    "uniswap",
}

CRYPTO_COLORS = {
    "avalanche": "#E84142",
    "axie infinity": "#00B8CE",
    "bitcoin": "#F7931A",
    "cardano": "#2A71D0",
    "chainlink": "#2A5ADA",
    "dogecoin": "#C2A633",
    "ethereum": "#8C8CFF",
    "fetch.ai": "#19D9D2",
    "litecoin": "#B8B8B8",
    "near protocol": "#7CE7D7",
    "polkadot": "#E6007A",
    "polygon": "#8247E5",
    "render": "#FF4D4D",
    "ripple": "#00AAE4",
    "shiba inu": "#F29E38",
    "solana": "#14F195",
    "stellar": "#A7B0C0",
    "sui": "#6FBCF0",
    "uniswap": "#FF007A",
}

FALLBACK_PALETTE = (
    "#6C8CFF",
    "#23D5AB",
    "#FF5E8A",
    "#B084FF",
    "#F4C95D",
    "#42C6FF",
    "#FF8A5B",
    "#71EFA3",
)

# Convenience mappings only. A CSV-provided Ticker column always wins.
DEFAULT_TICKERS = {
    "IE00B5BMR087": "SXR8.DE",
    "US0494681010": "TEAM",
    "US12468P1049": "AI",
    "CA1380357048": "CGC",
    "US67577C1053": "OCGN",
    "US70450Y1038": "PYPL",
    "US87918A1051": "TDOC",
    "US88034P1093": "TME",
    "US88339J1051": "TTD",
    "US9043111072": "UAA",
    "KYG970081173": "2269.HK",
    "KYG982AW1003": "XPEV",
    "XF000AVAX016": "AVAX-USD",
    "XF000AXS0014": "AXS-USD",
    "XF000DOT0011": "DOT-USD",
    "XF000FET0011": "FET-USD",
    "XF000MATIC12": "POL-USD",
    "XF0RENDER015": "RENDER-USD",
}


def normalize_label(value: object) -> str:
    """Return a stable ASCII-ish comparison key without changing display text."""

    text = str(value or "").strip().lower()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(char for char in text if not unicodedata.combining(char))
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def classify_asset(name: str, isin: str | None, explicit: str | None = None) -> str:
    """Classify an instrument using explicit data first, then conservative heuristics."""

    if explicit and str(explicit).strip():
        normalized = normalize_label(explicit)
        if "crypto" in normalized or "coin" in normalized:
            return "Crypto"
        if "etf" in normalized or "fund" in normalized:
            return "ETF"
        if "deriv" in normalized or "warrant" in normalized:
            return "Derivative"
        if "stock" in normalized or "equity" in normalized or "aktie" in normalized:
            return "Stock"

    name_key = normalize_label(name)
    isin_key = str(isin or "").upper().strip()
    if isin_key.startswith("XF") or name_key in CRYPTO_NAMES:
        return "Crypto"
    if any(token in name_key for token in ("short ", "long ", "knock out", "turbo", "warrant")):
        return "Derivative"
    if isin_key.startswith(("IE", "LU")) or any(
        token in name_key for token in (" etf", "s p 500", "msci", "index fund")
    ):
        return "ETF"
    if isin_key:
        return "Stock"
    return "Other"


def color_for_asset(name: str, isin: str | None = None) -> str:
    """Return a brand-like crypto color or a deterministic portfolio color."""

    key = normalize_label(name)
    if key in CRYPTO_COLORS:
        return CRYPTO_COLORS[key]
    digest = hashlib.sha256(f"{isin or ''}|{key}".encode("utf-8")).digest()
    return FALLBACK_PALETTE[digest[0] % len(FALLBACK_PALETTE)]


def ticker_for_asset(isin: str | None, csv_ticker: str | None = None) -> str | None:
    if csv_ticker and str(csv_ticker).strip():
        return str(csv_ticker).strip().upper()
    return DEFAULT_TICKERS.get(str(isin or "").upper().strip())
