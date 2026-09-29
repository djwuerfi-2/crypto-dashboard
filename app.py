"""Crypto Horizon — Streamlit dashboard for German crypto holding periods."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st
from streamlit_plotly_events import plotly_events

from crypto_holdings.charts import (
    PLOTLY_CONFIG,
    build_lot_timeline,
    build_position_timeline,
    build_tax_free_donut,
)
from crypto_holdings.data import dataframe_to_csv_bytes, load_transactions
from crypto_holdings.market import fetch_market_prices
from crypto_holdings.portfolio import analyze_portfolio
from crypto_holdings.styles import APP_CSS


ROOT = Path(__file__).resolve().parent
DEMO_FILE = ROOT / "sample_data" / "demo_transactions.csv"

st.set_page_config(
    page_title="Crypto Horizon",
    page_icon="◈",
    layout="wide",
    initial_sidebar_state="expanded",
)
st.markdown(APP_CSS, unsafe_allow_html=True)

# A lightweight deep link is useful for local previews and does not bypass the normal upload flow.
if "portfolio_bytes" not in st.session_state and st.query_params.get("demo") == "1":
    st.session_state["portfolio_bytes"] = DEMO_FILE.read_bytes()
    st.session_state["portfolio_name"] = "demo_transactions.csv"
    st.session_state["using_demo"] = True


@st.cache_data(show_spinner=False)
def cached_load(payload: bytes):
    return load_transactions(payload)


@st.cache_data(ttl=900, show_spinner=False)
def cached_prices(tickers: tuple[str, ...]) -> pd.DataFrame:
    return fetch_market_prices(tickers)


def fmt_units(value: float, kind: str) -> str:
    if kind == "€ proxy":
        return f"€{value:,.2f} proxy"
    return f"{value:,.6f}".rstrip("0").rstrip(" ").rstrip(".")


def render_landing() -> None:
    st.markdown(
        """
        <section class="hero-shell">
          <div class="hero-kicker">Private portfolio intelligence</div>
          <h1 class="hero-title">See when every crypto lot crosses its
            <span class="gradient">tax-free horizon.</span>
          </h1>
          <p class="hero-sub">
            Upload a transaction CSV. Crypto Horizon reconstructs FIFO lots, separates recorded
            holding history from projected maturity, and keeps every assumption visible.
            Your file stays inside this Streamlit session.
          </p>
        </section>
        <div class="feature-grid">
          <article class="feature-card">
            <div class="feature-icon">01 · TIMELINE</div>
            <h3>One portfolio, one time axis</h3>
            <p>Pan and zoom from closed equity positions to crypto lots that are still maturing.</p>
          </article>
          <article class="feature-card">
            <div class="feature-icon">02 · FIFO ENGINE</div>
            <h3>Lot-level clarity</h3>
            <p>Sales consume the oldest visible purchases first, with partial lots preserved.</p>
          </article>
          <article class="feature-card">
            <div class="feature-icon">03 · UNLOCK RADAR</div>
            <h3>Know what becomes eligible next</h3>
            <p>See the tax-free share today and upcoming one-year-plus-one-day milestones.</p>
          </article>
        </div>
        """,
        unsafe_allow_html=True,
    )

    upload_col, demo_col = st.columns([2.25, 1], gap="large")
    with upload_col:
        uploaded = st.file_uploader(
            "Upload transaction CSV",
            type=["csv"],
            help="Trade Republic tax exports work immediately. Add Quantity/Stück for tax-grade lot sizes.",
            key="landing_upload",
        )
        if uploaded is not None:
            st.session_state["portfolio_bytes"] = uploaded.getvalue()
            st.session_state["portfolio_name"] = uploaded.name
            st.rerun()
    with demo_col:
        st.markdown("#### No file at hand?")
        st.caption("Open a synthetic exact-quantity portfolio to explore every interaction.")
        if st.button("Launch demo portfolio", width="stretch", type="primary"):
            st.session_state["portfolio_bytes"] = DEMO_FILE.read_bytes()
            st.session_state["portfolio_name"] = "demo_transactions.csv"
            st.session_state["using_demo"] = True
            st.rerun()

    st.markdown(
        """
        <p class="micro-note">
          Best results: <b>Date</b>, <b>Transaction</b>, <b>Name</b>, <b>Total</b>,
          <b>Quantity</b>, and optionally <b>ISIN</b>, <b>Ticker</b>, <b>Asset Type</b>.
          Without Quantity, the dashboard uses clearly labelled transaction-value proxy units.
        </p>
        """,
        unsafe_allow_html=True,
    )


def render_warning_summary(warnings: list[str]) -> None:
    if not warnings:
        return
    with st.expander(f"Data notes · {len(warnings)}", expanded=False):
        for warning in warnings:
            st.warning(warning, icon="⚠️")


if "portfolio_bytes" not in st.session_state:
    render_landing()
    st.stop()

payload = st.session_state["portfolio_bytes"]
file_name = st.session_state.get("portfolio_name", "transactions.csv")
load_result = cached_load(payload)

with st.sidebar:
    st.markdown("## ◈ Crypto Horizon")
    st.caption("Holding-period command center")
    st.markdown("---")
    replacement = st.file_uploader("Replace CSV", type=["csv"], key="replacement_upload")
    if replacement is not None and replacement.getvalue() != payload:
        st.session_state["portfolio_bytes"] = replacement.getvalue()
        st.session_state["portfolio_name"] = replacement.name
        st.session_state["using_demo"] = False
        st.rerun()
    if st.button("Clear portfolio", width="stretch"):
        for key in (
            "portfolio_bytes",
            "portfolio_name",
            "using_demo",
            "selected_asset_key",
            "asset_inspector",
        ):
            st.session_state.pop(key, None)
        st.rerun()

if load_result.errors:
    st.error("The portfolio could not be loaded.")
    for error in load_result.errors:
        st.error(error, icon="🚫")
    render_warning_summary(load_result.warnings)
    st.stop()

today = pd.Timestamp.now().tz_localize(None)
analysis = analyze_portfolio(load_result.frame, as_of=today)
positions = analysis.positions.copy()
all_warnings = [*load_result.warnings, *analysis.warnings]

if analysis.is_empty:
    st.error("No portfolio positions could be reconstructed from the uploaded rows.")
    render_warning_summary(all_warnings)
    st.stop()

with st.sidebar:
    st.markdown("### View")
    available_types = sorted(positions["asset_type"].dropna().unique().tolist())
    selected_types = st.multiselect(
        "Asset classes",
        options=available_types,
        default=available_types,
        help="Select Crypto, Stock, ETF, Derivative, or Other.",
    )
    status_options = ["Active", "Closed", "Incomplete history"]
    selected_statuses = st.multiselect("Position status", status_options, default=status_options)
    sort_option = st.selectbox(
        "Sort positions",
        ["Position size · high to low", "Position size · low to high", "Name · A to Z"],
    )
    load_prices = st.toggle(
        "Load current market prices",
        value=False,
        help="Optional Yahoo Finance enrichment. Requires a Ticker mapping and network access.",
    )
    st.markdown("---")
    precision_label = "Exact lot quantities" if load_result.precision_mode == "exact-quantity" else "Value-proxy mode"
    st.markdown(f"<span class='status-pill'>{precision_label}</span>", unsafe_allow_html=True)
    st.caption(f"Source: {file_name}\n\nAs of {today:%d %b %Y, %H:%M}")

filtered = positions[positions["asset_type"].isin(selected_types)].copy()

def status_bucket(status: str) -> str:
    if str(status).startswith("Active"):
        return "Active"
    if str(status).startswith("Closed"):
        return "Closed"
    return "Incomplete history"


filtered = filtered[filtered["status"].map(status_bucket).isin(selected_statuses)]
if sort_option.startswith("Position size · high"):
    filtered = filtered.sort_values(["position_size", "asset_name"], ascending=[False, True])
elif sort_option.startswith("Position size · low"):
    filtered = filtered.sort_values(["position_size", "asset_name"], ascending=[True, True])
else:
    filtered = filtered.sort_values("asset_name", key=lambda values: values.str.casefold())

st.markdown(
    f"""
    <div class="dashboard-head">
      <div>
        <div class="section-kicker">Portfolio timeline</div>
        <h1 class="dashboard-title">Crypto Horizon</h1>
      </div>
      <div class="as-of">{file_name} · {today:%d %b %Y}</div>
    </div>
    """,
    unsafe_allow_html=True,
)
render_warning_summary(all_warnings)

if filtered.empty:
    st.info("No positions match the selected asset classes and statuses.")
    st.stop()

visible_keys = set(filtered["asset_key"])
active_count = int(filtered["status"].str.startswith("Active").sum())
remaining_cost = float(filtered["remaining_cost"].sum())
visible_crypto = analysis.crypto_status[analysis.crypto_status["asset_key"].isin(visible_keys)].copy()
crypto_total = float(visible_crypto["total_units"].sum()) if not visible_crypto.empty else 0.0
crypto_free = float(visible_crypto["tax_free_units"].sum()) if not visible_crypto.empty else 0.0
crypto_free_pct = 100 * crypto_free / crypto_total if crypto_total > 0 else 0.0
visible_unlocks = analysis.unlocks[analysis.unlocks["asset_key"].isin(visible_keys)].copy()
next_unlock = visible_unlocks["eligible_on"].min() if not visible_unlocks.empty else pd.NaT
unmatched_count = int(
    analysis.issues[
        (analysis.issues.get("asset_key", pd.Series(dtype=str)).isin(visible_keys))
        & (analysis.issues.get("issue", pd.Series(dtype=str)) == "SELL exceeds purchases visible in this CSV")
    ].shape[0]
) if not analysis.issues.empty else 0

kpi_cols = st.columns(5)
kpi_cols[0].metric("Active positions", f"{active_count}", help="Positions with remaining visible FIFO units.")
kpi_cols[1].metric("Recorded cost basis", f"€{remaining_cost:,.0f}", help="Remaining acquisition value from visible BUY rows.")
kpi_cols[2].metric("Crypto tax-free now", f"{crypto_free_pct:.0f}%", help="Weighted across visible active crypto lots.")
kpi_cols[3].metric(
    "Next unlock",
    f"{pd.Timestamp(next_unlock):%d %b}" if pd.notna(next_unlock) else "All clear",
    help=(
        f"Earliest future one-year-plus-one-day horizon: {pd.Timestamp(next_unlock):%d %b %Y, %H:%M}."
        if pd.notna(next_unlock)
        else "All visible crypto lots have crossed their horizon."
    ),
)
kpi_cols[4].metric("Unmatched sales", f"{unmatched_count}", help="SELL rows whose purchase is not present in this CSV.")

st.markdown("## Holding timeline")
st.markdown(
    "<p class='section-copy'>Solid bars are recorded holding windows. Faded crypto segments are projections to the latest outstanding lot unlock. Drag horizontally or use the mouse wheel to zoom; click a bar to inspect its FIFO lots.</p>",
    unsafe_allow_html=True,
)

timeline = build_position_timeline(filtered, today, filtered["asset_name"].tolist())
clicked_points = plotly_events(
    timeline,
    click_event=True,
    select_event=False,
    hover_event=False,
    override_height=590,
    override_width="100%",
    key="portfolio_timeline",
)
clicked_key = None
if clicked_points:
    clicked = clicked_points[-1]
    try:
        curve_number = int(clicked["curveNumber"])
        point_number = int(clicked.get("pointNumber", clicked.get("pointIndex", 0)))
        custom = timeline.data[curve_number].customdata[point_number]
        clicked_key = str(custom[0]) if custom else None
    except (IndexError, KeyError, TypeError, ValueError, AttributeError):
        clicked_key = None
if clicked_key in visible_keys:
    st.session_state["selected_asset_key"] = clicked_key
    st.session_state["asset_inspector"] = clicked_key

current_key = st.session_state.get("selected_asset_key")
if current_key not in visible_keys:
    current_key = str(filtered.iloc[0]["asset_key"])
    st.session_state["selected_asset_key"] = current_key

asset_options = filtered["asset_key"].tolist()
asset_labels = dict(zip(filtered["asset_key"], filtered["asset_name"], strict=False))
if st.session_state.get("asset_inspector") not in asset_options:
    st.session_state["asset_inspector"] = current_key

selected_key = st.selectbox(
    "Inspect position",
    asset_options,
    format_func=lambda value: asset_labels.get(value, value),
    key="asset_inspector",
    help="You can also click a bar in the timeline.",
)
st.session_state["selected_asset_key"] = selected_key
selected_position = filtered.loc[filtered["asset_key"] == selected_key].iloc[0]

st.markdown(f"## {selected_position['asset_name']} · lot detail")
detail_cols = st.columns([1, 1, 1, 1.25])
detail_cols[0].metric("Status", selected_position["status"])
detail_cols[1].metric(
    "Remaining",
    fmt_units(float(selected_position["position_size"]), str(selected_position["unit_kind"])),
)
detail_cols[2].metric("Visible cost", f"€{float(selected_position['remaining_cost']):,.2f}")
if selected_position["asset_type"] == "Crypto":
    detail_cols[3].metric("Tax-free share", f"{float(selected_position['tax_free_pct']):.1f}%")
else:
    detail_cols[3].metric("Instrument type", selected_position["asset_type"])

asset_lots = analysis.lots[analysis.lots["asset_key"] == selected_key]
if asset_lots.empty:
    st.warning("This asset only has unmatched SELL activity in the uploaded time window; no purchase lot can be reconstructed.")
else:
    lot_figure = build_lot_timeline(
        selected_key,
        analysis.lots,
        analysis.disposals,
        analysis.transactions,
        today,
    )
    st.plotly_chart(lot_figure, width="stretch", config=PLOTLY_CONFIG, key="lot_timeline")

with st.expander("Show selected transaction ledger", expanded=False):
    ledger = analysis.transactions[
        (analysis.transactions["asset_key"] == selected_key)
        & (analysis.transactions["transaction_type"].isin(["BUY", "SELL"]))
    ][["date", "transaction_type", "asset_name", "isin", "total", "net_amount"]].copy()
    ledger.columns = ["Date", "Type", "Asset", "ISIN", "Total", "Net amount"]
    st.dataframe(ledger.sort_values("Date", ascending=False), width="stretch", hide_index=True)

st.markdown("## Tax-free crypto capacity")
st.markdown(
    "<p class='section-copy'>Each ring shows the share of currently held, visible FIFO units whose one-year-plus-one-day horizon has passed. Grey remains inside the holding period.</p>",
    unsafe_allow_html=True,
)
if visible_crypto.empty:
    st.info("No active crypto positions are present in the current view.")
else:
    donut_rows = list(visible_crypto.iterrows())
    for start in range(0, len(donut_rows), 4):
        columns = st.columns(4)
        for column, (_, crypto_row) in zip(columns, donut_rows[start : start + 4], strict=False):
            with column:
                st.plotly_chart(
                    build_tax_free_donut(crypto_row),
                    width="stretch",
                    config={"displayModeBar": False, "displaylogo": False},
                    key=f"donut-{crypto_row['asset_key']}",
                )
                if pd.notna(crypto_row["next_unlock"]):
                    st.caption(
                        f"Next: {pd.Timestamp(crypto_row['next_unlock']):%d %b %Y} · "
                        f"{int(crypto_row['days_to_next_unlock'])} days"
                    )
                else:
                    st.caption("All visible remaining lots have matured.")

st.markdown("## Unlock radar")
st.markdown(
    "<p class='section-copy'>A compact action queue for crypto lots crossing the configured tax-free horizon.</p>",
    unsafe_allow_html=True,
)
radar_cols = st.columns(3)
within_30 = int((visible_unlocks["days_remaining"] <= 30).sum()) if not visible_unlocks.empty else 0
within_90 = int((visible_unlocks["days_remaining"] <= 90).sum()) if not visible_unlocks.empty else 0
later = max(len(visible_unlocks) - within_90, 0)
radar_cols[0].metric("Next 30 days", within_30)
radar_cols[1].metric("Next 90 days", within_90)
radar_cols[2].metric("Later", later)

if visible_unlocks.empty:
    st.success("No visible crypto lots are waiting for a future unlock.")
else:
    unlock_table = visible_unlocks[
        ["asset_name", "lot_number", "acquired_at", "eligible_on", "days_remaining", "units", "unit_kind", "precision"]
    ].copy()
    unlock_table.columns = [
        "Asset",
        "Lot",
        "Acquired",
        "Eligible",
        "Days left",
        "Amount",
        "Unit",
        "Precision",
    ]
    st.dataframe(unlock_table.head(30), width="stretch", hide_index=True)

if load_prices:
    st.markdown("## Market snapshot")
    price_candidates = filtered[
        (filtered["ticker"].notna()) & (filtered["ticker"] != "") & (filtered["position_size"] > 0)
    ].copy()
    if price_candidates.empty:
        st.info("No current positions have a known Ticker. Add a Ticker column to enable prices.")
    else:
        with st.spinner("Loading current prices…"):
            price_data = cached_prices(tuple(sorted(price_candidates["ticker"].dropna().unique())))
        market = price_candidates.merge(price_data, on="ticker", how="left")
        market["market_value"] = market.apply(
            lambda row: (
                float(row["position_size"]) * float(row["price"])
                if row["precision"] == "Exact quantity" and pd.notna(row["price"])
                else None
            ),
            axis=1,
        )
        market_view = market[["asset_name", "ticker", "price", "currency", "market_value", "error"]].copy()
        market_view.columns = ["Asset", "Ticker", "Last price", "Currency", "Market value", "Status"]
        st.dataframe(market_view, width="stretch", hide_index=True)
        st.caption("Indicative Yahoo Finance data, cached for 15 minutes. No price is used in holding-period calculations.")

st.markdown("## Data & calculation audit")
st.markdown(
    "<p class='section-copy'>Review exactly what was imported, which precision mode each asset uses, and where the CSV history is incomplete.</p>",
    unsafe_allow_html=True,
)
audit_left, audit_right = st.columns([1.15, 1], gap="large")
with audit_left:
    st.markdown("#### Position export")
    export_columns = [
        "asset_name",
        "isin",
        "asset_type",
        "status",
        "position_size",
        "unit_kind",
        "remaining_cost",
        "tax_free_units",
        "locked_units",
        "tax_free_pct",
        "start",
        "end",
        "projection_end",
        "precision",
    ]
    export_frame = positions[export_columns].copy()
    st.download_button(
        "Download calculated positions",
        data=dataframe_to_csv_bytes(export_frame),
        file_name="crypto_horizon_positions.csv",
        mime="text/csv",
        width="stretch",
    )
    st.caption(f"{len(load_result.frame)} imported rows · {len(positions)} reconstructed positions · {load_result.encoding}")
with audit_right:
    st.markdown("#### Scope")
    st.markdown(
        """
        - FIFO is applied per ISIN (or per name when ISIN is missing).
        - Crypto eligibility is acquisition time + one calendar year + one safety day.
        - Stocks, ETFs, and derivatives do not receive the crypto tax-free status.
        - Market prices never change the FIFO or eligibility result.
        """
    )

with st.expander("Incomplete history and unmatched sales", expanded=not analysis.issues.empty):
    if analysis.issues.empty:
        st.success("No unmatched sale or unusable trade amount was detected.")
    else:
        issues_view = analysis.issues.copy()
        issues_view.columns = [str(column).replace("_", " ").title() for column in issues_view.columns]
        st.dataframe(issues_view, width="stretch", hide_index=True)

with st.expander("Normalized source preview", expanded=False):
    preview_columns = [
        column
        for column in ("date", "transaction_type", "asset_name", "isin", "total", "net_amount", "quantity", "ticker")
        if column in load_result.frame.columns
    ]
    st.dataframe(load_result.frame[preview_columns].head(50), width="stretch", hide_index=True)

st.info(
    "Planning aid, not tax advice. The holding-period model follows §23 EStG and the German Federal Ministry of Finance guidance dated 6 March 2025. Confirm taxable treatment, staking/lending, transfers, and missing opening inventory with a tax professional.",
    icon="ℹ️",
)
