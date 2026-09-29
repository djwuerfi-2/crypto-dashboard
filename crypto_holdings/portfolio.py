"""FIFO lot matching and holding-period analytics."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

import pandas as pd

from .config import classify_asset, color_for_asset, ticker_for_asset


EPSILON = 1e-9


@dataclass(slots=True)
class PortfolioAnalysis:
    transactions: pd.DataFrame
    positions: pd.DataFrame
    lots: pd.DataFrame
    disposals: pd.DataFrame
    crypto_status: pd.DataFrame
    unlocks: pd.DataFrame
    issues: pd.DataFrame
    as_of: pd.Timestamp
    warnings: list[str] = field(default_factory=list)

    @property
    def is_empty(self) -> bool:
        return self.positions.empty


def eligibility_date(acquired_at: pd.Timestamp) -> pd.Timestamp:
    """One calendar year plus one safety day, preserving the acquisition time."""

    return acquired_at + pd.DateOffset(years=1, days=1)


def _asset_key(row: pd.Series) -> str:
    isin = str(row.get("isin", "") or "").strip().upper()
    name = str(row.get("asset_name", "") or "").strip()
    return isin or f"NAME::{name.casefold()}"


def _empty(columns: list[str]) -> pd.DataFrame:
    return pd.DataFrame(columns=columns)


def analyze_portfolio(
    frame: pd.DataFrame,
    as_of: date | datetime | pd.Timestamp | None = None,
) -> PortfolioAnalysis:
    """Apply per-asset FIFO and calculate current crypto maturity."""

    if as_of is None:
        as_of_ts = pd.Timestamp.now().tz_localize(None)
    else:
        as_of_ts = pd.Timestamp(as_of)
        if as_of_ts.tzinfo is not None:
            as_of_ts = as_of_ts.tz_localize(None)

    transactions = frame.copy()
    if transactions.empty:
        return PortfolioAnalysis(
            transactions=transactions,
            positions=_empty([]),
            lots=_empty([]),
            disposals=_empty([]),
            crypto_status=_empty([]),
            unlocks=_empty([]),
            issues=_empty([]),
            as_of=as_of_ts,
        )

    transactions["asset_key"] = transactions.apply(_asset_key, axis=1)
    transactions["asset_type"] = transactions.apply(
        lambda row: classify_asset(
            str(row.get("asset_name", "")),
            str(row.get("isin", "")),
            str(row.get("asset_type_input", "")),
        ),
        axis=1,
    )
    transactions["color"] = transactions.apply(
        lambda row: color_for_asset(str(row.get("asset_name", "")), str(row.get("isin", ""))),
        axis=1,
    )
    transactions["market_ticker"] = transactions.apply(
        lambda row: ticker_for_asset(str(row.get("isin", "")), str(row.get("ticker", ""))),
        axis=1,
    )

    future_mask = transactions["date"] > as_of_ts
    warnings: list[str] = []
    if future_mask.any():
        warnings.append(f"Excluded {int(future_mask.sum())} transaction(s) dated after the as-of time.")
    eligible_transactions = transactions.loc[~future_mask].copy()
    trade_rows = eligible_transactions[
        eligible_transactions["transaction_type"].isin(["BUY", "SELL"])
    ].sort_values(["date", "transaction_id"], kind="stable")

    lot_records: list[dict[str, Any]] = []
    disposal_records: list[dict[str, Any]] = []
    position_records: list[dict[str, Any]] = []
    issue_records: list[dict[str, Any]] = []
    crypto_records: list[dict[str, Any]] = []
    unlock_records: list[dict[str, Any]] = []

    for asset_key, group in trade_rows.groupby("asset_key", sort=False):
        group = group.sort_values(["date", "transaction_id"], kind="stable")
        meta = group.iloc[-1]
        name = str(meta["asset_name"])
        isin = str(meta.get("isin", ""))
        asset_type = str(meta["asset_type"])
        color = str(meta["color"])
        market_ticker = meta.get("market_ticker")

        quantity_is_exact = (
            "quantity" in group.columns
            and group["quantity"].notna().all()
            and (group["quantity"].abs() > EPSILON).all()
        )
        unit_kind = "units" if quantity_is_exact else "€ proxy"
        precision = "Exact quantity" if quantity_is_exact else "Value proxy"

        open_lots: list[dict[str, Any]] = []
        all_lots: list[dict[str, Any]] = []
        asset_disposals: list[dict[str, Any]] = []
        unmatched_units = 0.0
        lot_counter = 0

        for _, row in group.iterrows():
            amount = row.get("total")
            if pd.isna(amount):
                amount = row.get("net_amount")
            amount_value = abs(float(amount)) if pd.notna(amount) else 0.0
            if quantity_is_exact:
                trade_units = abs(float(row["quantity"]))
            else:
                trade_units = amount_value

            if trade_units <= EPSILON:
                issue_records.append(
                    {
                        "asset_key": asset_key,
                        "asset_name": name,
                        "date": row["date"],
                        "issue": "Trade has no usable quantity or amount",
                        "severity": "warning",
                        "units": 0.0,
                        "unit_kind": unit_kind,
                    }
                )
                continue

            if row["transaction_type"] == "BUY":
                lot_counter += 1
                lot = {
                    "asset_key": asset_key,
                    "asset_name": name,
                    "isin": isin,
                    "asset_type": asset_type,
                    "color": color,
                    "ticker": market_ticker,
                    "lot_id": f"{asset_key}-lot-{lot_counter:03d}",
                    "lot_number": lot_counter,
                    "acquired_at": row["date"],
                    "eligible_on": eligibility_date(row["date"]) if asset_type == "Crypto" else pd.NaT,
                    "original_units": trade_units,
                    "remaining_units": trade_units,
                    "cost_total": amount_value,
                    "unit_kind": unit_kind,
                    "precision": precision,
                    "source_transaction_id": row["transaction_id"],
                }
                open_lots.append(lot)
                all_lots.append(lot)
                continue

            remaining_to_sell = trade_units
            while remaining_to_sell > EPSILON and open_lots:
                lot = open_lots[0]
                matched = min(float(lot["remaining_units"]), remaining_to_sell)
                disposal = {
                    "asset_key": asset_key,
                    "asset_name": name,
                    "isin": isin,
                    "asset_type": asset_type,
                    "color": color,
                    "lot_id": lot["lot_id"],
                    "lot_number": lot["lot_number"],
                    "acquired_at": lot["acquired_at"],
                    "disposed_at": row["date"],
                    "units": matched,
                    "unit_kind": unit_kind,
                    "precision": precision,
                    "holding_days": (row["date"] - lot["acquired_at"]).total_seconds() / 86400,
                    "eligible_on": lot["eligible_on"],
                    "tax_free_at_disposal": bool(
                        asset_type == "Crypto" and row["date"] >= lot["eligible_on"]
                    ),
                    "source_transaction_id": row["transaction_id"],
                }
                disposal_records.append(disposal)
                asset_disposals.append(disposal)
                lot["remaining_units"] = float(lot["remaining_units"]) - matched
                remaining_to_sell -= matched
                if float(lot["remaining_units"]) <= EPSILON:
                    lot["remaining_units"] = 0.0
                    open_lots.pop(0)

            if remaining_to_sell > EPSILON:
                unmatched_units += remaining_to_sell
                issue_records.append(
                    {
                        "asset_key": asset_key,
                        "asset_name": name,
                        "date": row["date"],
                        "issue": "SELL exceeds purchases visible in this CSV",
                        "severity": "incomplete history",
                        "units": remaining_to_sell,
                        "unit_kind": unit_kind,
                    }
                )

        for lot in all_lots:
            original = float(lot["original_units"])
            remaining = float(lot["remaining_units"])
            lot["remaining_cost"] = (
                float(lot["cost_total"]) * remaining / original if original > EPSILON else 0.0
            )
            if remaining <= EPSILON:
                lot["status"] = "Closed"
            elif remaining < original - EPSILON:
                lot["status"] = "Partially held"
            else:
                lot["status"] = "Held"
            lot["is_tax_free_now"] = bool(
                asset_type == "Crypto"
                and remaining > EPSILON
                and as_of_ts >= lot["eligible_on"]
            )
            lot_records.append(lot.copy())

        remaining_lots = [lot for lot in all_lots if float(lot["remaining_units"]) > EPSILON]
        remaining_units = sum(float(lot["remaining_units"]) for lot in remaining_lots)
        remaining_cost = sum(float(lot["remaining_cost"]) for lot in remaining_lots)
        first_trade_at = group["date"].min()
        first_buy_at = min((lot["acquired_at"] for lot in all_lots), default=first_trade_at)
        last_trade_at = group["date"].max()
        last_disposal_at = max(
            (record["disposed_at"] for record in asset_disposals),
            default=last_trade_at,
        )

        if remaining_units > EPSILON:
            status = "Active"
            timeline_end = as_of_ts
        elif all_lots:
            status = "Closed"
            timeline_end = last_disposal_at
        else:
            status = "Incomplete history"
            timeline_end = last_trade_at
        if unmatched_units > EPSILON and status != "Incomplete history":
            status = f"{status} · incomplete history"

        future_unlocks = [
            lot["eligible_on"]
            for lot in remaining_lots
            if asset_type == "Crypto" and lot["eligible_on"] > as_of_ts
        ]
        projection_end = max(future_unlocks, default=timeline_end)
        free_units = sum(
            float(lot["remaining_units"])
            for lot in remaining_lots
            if asset_type == "Crypto" and as_of_ts >= lot["eligible_on"]
        )
        locked_units = max(remaining_units - free_units, 0.0) if asset_type == "Crypto" else 0.0

        position_records.append(
            {
                "asset_key": asset_key,
                "asset_name": name,
                "isin": isin,
                "asset_type": asset_type,
                "color": color,
                "ticker": market_ticker,
                "start": first_buy_at,
                "end": timeline_end,
                "projection_end": projection_end,
                "status": status,
                "position_size": remaining_units,
                "remaining_cost": remaining_cost,
                "unit_kind": unit_kind,
                "precision": precision,
                "buy_count": int((group["transaction_type"] == "BUY").sum()),
                "sell_count": int((group["transaction_type"] == "SELL").sum()),
                "unmatched_sell_units": unmatched_units,
                "tax_free_units": free_units,
                "locked_units": locked_units,
                "tax_free_pct": (100 * free_units / remaining_units) if remaining_units > EPSILON else 0.0,
            }
        )

        if asset_type == "Crypto" and remaining_units > EPSILON:
            next_unlock = min(future_unlocks, default=pd.NaT)
            crypto_records.append(
                {
                    "asset_key": asset_key,
                    "asset_name": name,
                    "isin": isin,
                    "color": color,
                    "total_units": remaining_units,
                    "tax_free_units": free_units,
                    "locked_units": locked_units,
                    "tax_free_pct": 100 * free_units / remaining_units,
                    "next_unlock": next_unlock,
                    "days_to_next_unlock": (
                        max(int((next_unlock - as_of_ts).total_seconds() // 86400) + 1, 0)
                        if pd.notna(next_unlock)
                        else None
                    ),
                    "unit_kind": unit_kind,
                    "precision": precision,
                }
            )

            for lot in remaining_lots:
                if lot["eligible_on"] > as_of_ts:
                    unlock_records.append(
                        {
                            "asset_key": asset_key,
                            "asset_name": name,
                            "color": color,
                            "lot_id": lot["lot_id"],
                            "lot_number": lot["lot_number"],
                            "acquired_at": lot["acquired_at"],
                            "eligible_on": lot["eligible_on"],
                            "days_remaining": max(
                                int((lot["eligible_on"] - as_of_ts).total_seconds() // 86400) + 1,
                                0,
                            ),
                            "units": float(lot["remaining_units"]),
                            "unit_kind": unit_kind,
                            "precision": precision,
                        }
                    )

    positions = pd.DataFrame(position_records)
    lots = pd.DataFrame(lot_records)
    disposals = pd.DataFrame(disposal_records)
    crypto_status = pd.DataFrame(crypto_records)
    unlocks = pd.DataFrame(unlock_records)
    issues = pd.DataFrame(issue_records)

    if not positions.empty:
        positions = positions.sort_values(["asset_name"], key=lambda s: s.str.casefold()).reset_index(drop=True)
    if not lots.empty:
        lots = lots.sort_values(["asset_name", "acquired_at", "lot_number"], kind="stable").reset_index(drop=True)
    if not disposals.empty:
        disposals = disposals.sort_values(["disposed_at", "asset_name"], kind="stable").reset_index(drop=True)
    if not crypto_status.empty:
        crypto_status = crypto_status.sort_values(
            ["tax_free_pct", "asset_name"], ascending=[False, True]
        ).reset_index(drop=True)
    if not unlocks.empty:
        unlocks = unlocks.sort_values(["eligible_on", "asset_name"], kind="stable").reset_index(drop=True)

    return PortfolioAnalysis(
        transactions=transactions,
        positions=positions,
        lots=lots,
        disposals=disposals,
        crypto_status=crypto_status,
        unlocks=unlocks,
        issues=issues,
        as_of=as_of_ts,
        warnings=warnings,
    )
