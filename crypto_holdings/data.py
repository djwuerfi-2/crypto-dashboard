"""CSV ingestion and normalization for broker transaction exports."""

from __future__ import annotations

from dataclasses import dataclass, field
from html import unescape
from io import BytesIO, StringIO
import re
import unicodedata
from typing import BinaryIO

import pandas as pd


CANONICAL_ALIASES = {
    "date": {"datum", "date", "timestamp", "datetime", "zeitpunkt"},
    "transaction_type": {
        "transaktionen",
        "transaktion",
        "transaction",
        "transaction type",
        "type",
        "typ",
    },
    "isin": {"isin", "instrument isin"},
    "asset_name": {"name", "asset", "asset name", "instrument", "wertpapier"},
    "total": {"total", "betrag", "gross amount", "trade value", "wert"},
    "net_amount": {"summe", "net", "net amount", "cash amount"},
    "quantity": {
        "quantity",
        "qty",
        "stuck",
        "stueck",
        "anzahl",
        "menge",
        "shares",
        "units",
        "coins",
    },
    "ticker": {"ticker", "symbol", "yahoo ticker", "market symbol"},
    "asset_type_input": {"asset type", "asset class", "anlageklasse", "klasse"},
    "fees": {"fees", "fee", "gebuhr", "gebuhren", "kosten"},
}

NUMERIC_COLUMNS = ("total", "net_amount", "quantity", "fees")
TRADE_TYPES = {"BUY", "SELL"}


@dataclass(slots=True)
class DataLoadResult:
    frame: pd.DataFrame
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    encoding: str = "utf-8"
    column_map: dict[str, str] = field(default_factory=dict)
    precision_mode: str = "value-proxy"

    @property
    def is_valid(self) -> bool:
        return not self.errors and not self.frame.empty


def _header_key(value: object) -> str:
    text = unescape(str(value or "")).replace("**", "").strip()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(char for char in text if not unicodedata.combining(char))
    return re.sub(r"[^a-zA-Z0-9]+", " ", text).strip().lower()


def _canonical_name(value: object) -> str | None:
    key = _header_key(value)
    for canonical, aliases in CANONICAL_ALIASES.items():
        if key in aliases:
            return canonical
    return None


def _decode_csv(raw: bytes) -> tuple[str, str]:
    for encoding in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            return raw.decode(encoding), encoding
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace"), "utf-8 (replacement characters)"


def parse_number(value: object) -> float | None:
    """Parse common German and English number formats into a float."""

    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    if isinstance(value, (int, float)):
        return float(value)

    text = str(value).strip()
    if not text or text.lower() in {"nan", "none", "-"}:
        return None
    negative_parentheses = text.startswith("(") and text.endswith(")")
    text = re.sub(r"[^0-9,.'+\-]", "", text).replace("'", "")
    if not text:
        return None

    if "," in text and "." in text:
        if text.rfind(",") > text.rfind("."):
            text = text.replace(".", "").replace(",", ".")
        else:
            text = text.replace(",", "")
    elif "," in text:
        # German broker exports use a decimal comma, including high-precision quantities
        # such as 0,125. Multiple commas are treated as grouping separators.
        comma_parts = text.split(",")
        text = text.replace(",", "") if len(comma_parts) > 2 else text.replace(",", ".")

    try:
        number = float(text)
    except ValueError:
        return None
    return -abs(number) if negative_parentheses else number


def _read_bytes(source: bytes | bytearray | BinaryIO) -> bytes:
    if isinstance(source, (bytes, bytearray)):
        return bytes(source)
    if hasattr(source, "getvalue"):
        return bytes(source.getvalue())
    if hasattr(source, "read"):
        payload = source.read()
        return payload if isinstance(payload, bytes) else str(payload).encode("utf-8")
    raise TypeError("CSV source must be bytes or a binary file-like object.")


def load_transactions(source: bytes | bytearray | BinaryIO) -> DataLoadResult:
    """Load a CSV and normalize its trade columns without mutating the source."""

    warnings: list[str] = []
    errors: list[str] = []

    try:
        raw = _read_bytes(source)
    except (TypeError, OSError) as exc:
        return DataLoadResult(pd.DataFrame(), errors=[str(exc)])

    if not raw:
        return DataLoadResult(pd.DataFrame(), errors=["The uploaded CSV is empty."])

    text, encoding = _decode_csv(raw)
    try:
        frame = pd.read_csv(StringIO(text), sep=None, engine="python", dtype=str)
    except Exception as exc:  # pandas emits several parser-specific exception classes
        return DataLoadResult(
            pd.DataFrame(),
            errors=[f"The CSV could not be parsed: {exc}"],
            encoding=encoding,
        )

    frame.columns = [unescape(str(column)).replace("**", "").strip() for column in frame.columns]
    column_map: dict[str, str] = {}
    rename_map: dict[str, str] = {}
    for source_name in frame.columns:
        canonical = _canonical_name(source_name)
        if canonical and canonical not in column_map:
            column_map[canonical] = source_name
            rename_map[source_name] = canonical
    frame = frame.rename(columns=rename_map)

    required = {"date", "transaction_type", "asset_name"}
    missing = sorted(required - set(frame.columns))
    if missing:
        errors.append(
            "Missing required columns: " + ", ".join(missing) + ". "
            "Expected columns comparable to Datum, Transaktionen, and Name."
        )
        return DataLoadResult(
            frame,
            warnings=warnings,
            errors=errors,
            encoding=encoding,
            column_map=column_map,
        )

    if "total" not in frame.columns and "net_amount" not in frame.columns:
        errors.append("Missing an amount column. Add Total, Summe, or a supported equivalent.")

    for column in NUMERIC_COLUMNS:
        if column in frame.columns:
            frame[column] = frame[column].map(parse_number).astype("Float64")

    if "total" not in frame.columns and "net_amount" in frame.columns:
        frame["total"] = frame["net_amount"]
        warnings.append("Total was not present; Net amount is used as the trade value.")
    if "net_amount" not in frame.columns:
        frame["net_amount"] = frame.get("total", pd.Series(dtype="Float64"))

    frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
    invalid_dates = int(frame["date"].isna().sum())
    if invalid_dates:
        warnings.append(f"Ignored {invalid_dates} row(s) with an invalid date.")
        frame = frame.loc[frame["date"].notna()].copy()

    frame["transaction_type"] = (
        frame["transaction_type"].fillna("").astype(str).str.strip().str.upper()
    )
    frame["asset_name"] = frame["asset_name"].fillna("").astype(str).str.strip()
    if "isin" not in frame.columns:
        frame["isin"] = ""
    frame["isin"] = frame["isin"].fillna("").astype(str).str.strip().str.upper()
    for optional in ("ticker", "asset_type_input"):
        if optional not in frame.columns:
            frame[optional] = ""
        frame[optional] = frame[optional].fillna("").astype(str).str.strip()

    blank_assets = (frame["asset_name"] == "") & frame["transaction_type"].isin(TRADE_TYPES)
    if blank_assets.any():
        warnings.append(f"Ignored {int(blank_assets.sum())} trade row(s) without an asset name.")
        frame = frame.loc[~blank_assets].copy()

    trades = frame[frame["transaction_type"].isin(TRADE_TYPES)]
    if trades.empty:
        errors.append("No BUY or SELL transactions were found.")

    exact_quantity = (
        "quantity" in trades.columns
        and not trades.empty
        and trades["quantity"].notna().all()
        and (trades["quantity"].abs() > 0).all()
    )
    precision_mode = "exact-quantity" if exact_quantity else "value-proxy"
    if not exact_quantity:
        warnings.append(
            "No complete Quantity/Stück column was found. Remaining holdings and tax-free shares "
            "use transaction-value proxy units and are directional, not tax-grade quantities."
        )

    if "�" in text:
        warnings.append("The source file contains replacement characters; some instrument names may look damaged.")

    frame = frame.sort_values(["date"], kind="stable").reset_index(drop=True)
    frame["transaction_id"] = [f"tx-{index + 1:04d}" for index in range(len(frame))]

    return DataLoadResult(
        frame=frame,
        warnings=warnings,
        errors=errors,
        encoding=encoding,
        column_map=column_map,
        precision_mode=precision_mode,
    )


def dataframe_to_csv_bytes(frame: pd.DataFrame) -> bytes:
    return frame.to_csv(index=False).encode("utf-8-sig")


def bytes_buffer(payload: bytes) -> BytesIO:
    """Small public helper used by tests and demo plumbing."""

    return BytesIO(payload)
