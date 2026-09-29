"""Plotly figures for portfolio and lot-level holding timelines."""

from __future__ import annotations

from collections.abc import Iterable

import pandas as pd
import plotly.graph_objects as go


PAPER = "rgba(0,0,0,0)"
GRID = "rgba(139, 156, 190, 0.12)"
TEXT = "#E8EDF8"
MUTED = "#8A97B1"


def _duration_ms(start: pd.Timestamp, end: pd.Timestamp) -> float:
    return max((pd.Timestamp(end) - pd.Timestamp(start)).total_seconds() * 1000, 3_600_000)


def _base_layout(fig: go.Figure, height: int) -> go.Figure:
    fig.update_layout(
        height=height,
        paper_bgcolor=PAPER,
        plot_bgcolor=PAPER,
        font={"family": "Inter, ui-sans-serif, system-ui", "color": TEXT, "size": 12},
        margin={"l": 12, "r": 18, "t": 24, "b": 28},
        hoverlabel={"bgcolor": "#11182A", "bordercolor": "#2B3A59", "font_color": TEXT},
        legend={
            "orientation": "h",
            "yanchor": "bottom",
            "y": 1.01,
            "xanchor": "right",
            "x": 1,
            "font": {"color": MUTED, "size": 11},
        },
        clickmode="event+select",
        dragmode="pan",
        bargap=0.38,
        selectdirection="h",
    )
    return fig


def build_position_timeline(
    positions: pd.DataFrame,
    as_of: pd.Timestamp,
    order: Iterable[str] | None = None,
) -> go.Figure:
    """Create the fixed-height, pannable overview timeline."""

    fig = go.Figure()
    ordered_names = list(order or positions["asset_name"].tolist())

    for _, row in positions.iterrows():
        start = pd.Timestamp(row["start"])
        end = pd.Timestamp(row["end"])
        custom = [[row["asset_key"], row["asset_name"], "observed"]]
        fig.add_trace(
            go.Bar(
                x=[_duration_ms(start, end)],
                base=[start],
                y=[row["asset_name"]],
                orientation="h",
                marker={
                    "color": row["color"],
                    "line": {"color": "rgba(255,255,255,0.26)", "width": 1},
                },
                width=0.5,
                name="Recorded holding window",
                legendgroup="observed",
                showlegend=False,
                customdata=custom,
                hovertemplate=(
                    "<b>%{y}</b><br>"
                    f"{row['asset_type']} · {row['status']}<br>"
                    f"Start: {start:%d %b %Y}<br>"
                    f"Observed through: {end:%d %b %Y}<br>"
                    f"Position: {float(row['position_size']):,.4f} {row['unit_kind']}<br>"
                    "<extra>Click to inspect lots</extra>"
                ),
                selected={"marker": {"opacity": 1.0}},
                unselected={"marker": {"opacity": 0.5}},
            )
        )

        projection_end = pd.Timestamp(row["projection_end"])
        if row["asset_type"] == "Crypto" and projection_end > as_of and end >= as_of:
            fig.add_trace(
                go.Bar(
                    x=[_duration_ms(as_of, projection_end)],
                    base=[as_of],
                    y=[row["asset_name"]],
                    orientation="h",
                    marker={
                        "color": row["color"],
                        "opacity": 0.24,
                        "line": {"color": row["color"], "width": 1},
                        "pattern": {"shape": "/", "solidity": 0.12},
                    },
                    width=0.5,
                    name="Projected until final unlock",
                    legendgroup="projection",
                    showlegend=False,
                    customdata=[[row["asset_key"], row["asset_name"], "projection"]],
                    hovertemplate=(
                        "<b>%{y}</b><br>Projected maturity path<br>"
                        f"Final recorded-lot unlock: {projection_end:%d %b %Y}"
                        "<extra>Click to inspect lots</extra>"
                    ),
                )
            )
            fig.add_trace(
                go.Scatter(
                    x=[projection_end],
                    y=[row["asset_name"]],
                    mode="markers",
                    marker={"symbol": "diamond", "size": 8, "color": row["color"]},
                    showlegend=False,
                    customdata=[[row["asset_key"], row["asset_name"], "unlock"]],
                    hovertemplate=(
                        "<b>%{y}</b><br>Final recorded-lot unlock<br>"
                        f"{projection_end:%d %b %Y}<extra></extra>"
                    ),
                )
            )

    fig.add_vline(x=as_of, line_width=1.5, line_dash="dot", line_color="#F8FAFC")
    fig.add_annotation(
        x=as_of,
        y=1.02,
        yref="paper",
        text="TODAY",
        showarrow=False,
        font={"size": 10, "color": "#F8FAFC"},
        bgcolor="#1B2540",
        borderpad=4,
    )

    initial_start = as_of - pd.DateOffset(months=3)
    initial_end = as_of + pd.DateOffset(months=3)
    _base_layout(fig, height=560)
    fig.update_layout(barmode="overlay", hovermode="closest")
    fig.update_xaxes(
        type="date",
        range=[initial_start, initial_end],
        rangeslider={"visible": True, "thickness": 0.08, "bgcolor": "rgba(20,28,48,0.7)"},
        rangeselector={
            "buttons": [
                {"count": 3, "label": "3M", "step": "month", "stepmode": "backward"},
                {"count": 6, "label": "6M", "step": "month", "stepmode": "backward"},
                {"count": 1, "label": "1Y", "step": "year", "stepmode": "backward"},
                {"step": "all", "label": "ALL"},
            ],
            "x": 0,
            "y": 1.09,
            "font": {"color": MUTED, "size": 10},
            "bgcolor": "rgba(18,26,45,0.9)",
            "activecolor": "#33436A",
        },
        gridcolor=GRID,
        tickformat="%b\n%Y",
        showline=False,
        zeroline=False,
        fixedrange=False,
    )
    fig.update_yaxes(
        categoryorder="array",
        categoryarray=list(reversed(ordered_names)),
        fixedrange=False,
        tickfont={"color": TEXT, "size": 12},
        automargin=True,
        gridcolor="rgba(0,0,0,0)",
    )
    return fig


def build_lot_timeline(
    asset_key: str,
    lots: pd.DataFrame,
    disposals: pd.DataFrame,
    transactions: pd.DataFrame,
    as_of: pd.Timestamp,
) -> go.Figure:
    """Create a transaction-lot drill-down for one selected asset."""

    selected_lots = lots[lots["asset_key"] == asset_key].copy()
    selected_disposals = disposals[disposals["asset_key"] == asset_key].copy()
    selected_transactions = transactions[
        (transactions["asset_key"] == asset_key)
        & transactions["transaction_type"].isin(["BUY", "SELL"])
    ].copy()
    fig = go.Figure()
    rows: list[str] = []

    for _, lot in selected_lots.iterrows():
        color = lot["color"]
        lot_disposals = selected_disposals[selected_disposals["lot_id"] == lot["lot_id"]]
        for segment_number, (_, sale) in enumerate(lot_disposals.iterrows(), start=1):
            label = f"Lot {int(lot['lot_number']):02d} · sold {segment_number}"
            rows.append(label)
            fig.add_trace(
                go.Bar(
                    x=[_duration_ms(lot["acquired_at"], sale["disposed_at"])],
                    base=[lot["acquired_at"]],
                    y=[label],
                    orientation="h",
                    width=0.46,
                    marker={"color": color, "line": {"color": "rgba(255,255,255,.25)", "width": 1}},
                    showlegend=False,
                    hovertemplate=(
                        f"<b>Lot {int(lot['lot_number']):02d}</b><br>"
                        f"Bought: {pd.Timestamp(lot['acquired_at']):%d %b %Y, %H:%M}<br>"
                        f"Sold: {pd.Timestamp(sale['disposed_at']):%d %b %Y, %H:%M}<br>"
                        f"Matched: {float(sale['units']):,.6f} {sale['unit_kind']}<br>"
                        f"Held: {float(sale['holding_days']):,.0f} days<br>"
                        f"Tax-free at sale: {'Yes' if sale['tax_free_at_disposal'] else 'No / n.a.'}"
                        "<extra></extra>"
                    ),
                )
            )
            fig.add_trace(
                go.Scatter(
                    x=[sale["disposed_at"]],
                    y=[label],
                    mode="markers",
                    marker={"symbol": "x", "size": 9, "color": "#FF6B7A", "line": {"width": 1}},
                    showlegend=False,
                    hovertemplate="SELL<extra></extra>",
                )
            )

        if float(lot["remaining_units"]) > 1e-9:
            label = f"Lot {int(lot['lot_number']):02d} · held"
            rows.append(label)
            fig.add_trace(
                go.Bar(
                    x=[_duration_ms(lot["acquired_at"], as_of)],
                    base=[lot["acquired_at"]],
                    y=[label],
                    orientation="h",
                    width=0.46,
                    marker={"color": color, "line": {"color": "rgba(255,255,255,.25)", "width": 1}},
                    showlegend=False,
                    hovertemplate=(
                        f"<b>Lot {int(lot['lot_number']):02d}</b><br>"
                        f"Bought: {pd.Timestamp(lot['acquired_at']):%d %b %Y, %H:%M}<br>"
                        f"Remaining: {float(lot['remaining_units']):,.6f} {lot['unit_kind']}<br>"
                        f"Status: {lot['status']}<extra></extra>"
                    ),
                )
            )
            if lot["asset_type"] == "Crypto" and pd.Timestamp(lot["eligible_on"]) > as_of:
                fig.add_trace(
                    go.Bar(
                        x=[_duration_ms(as_of, lot["eligible_on"])],
                        base=[as_of],
                        y=[label],
                        orientation="h",
                        width=0.46,
                        marker={
                            "color": color,
                            "opacity": 0.24,
                            "pattern": {"shape": "/", "solidity": 0.12},
                        },
                        showlegend=False,
                        hovertemplate=(
                            "Projected maturity path<br>"
                            f"Eligible: {pd.Timestamp(lot['eligible_on']):%d %b %Y, %H:%M}"
                            "<extra></extra>"
                        ),
                    )
                )
                fig.add_trace(
                    go.Scatter(
                        x=[lot["eligible_on"]],
                        y=[label],
                        mode="markers",
                        marker={"symbol": "diamond", "size": 8, "color": color},
                        showlegend=False,
                        hovertemplate="Tax-free horizon<extra></extra>",
                    )
                )

    # If the file begins with SELLs, expose those events even though no purchase lot can be reconstructed.
    unmatched_sells = selected_transactions[
        (selected_transactions["transaction_type"] == "SELL")
        & (~selected_transactions["transaction_id"].isin(selected_disposals.get("source_transaction_id", [])))
    ]
    if not unmatched_sells.empty:
        label = "Opening inventory · unmatched sells"
        rows.append(label)
        fig.add_trace(
            go.Scatter(
                x=unmatched_sells["date"],
                y=[label] * len(unmatched_sells),
                mode="markers",
                marker={"symbol": "x", "size": 10, "color": "#FFB454"},
                showlegend=False,
                hovertemplate="SELL with purchase outside CSV<extra></extra>",
            )
        )

    fig.add_vline(x=as_of, line_width=1.25, line_dash="dot", line_color="#F8FAFC")
    _base_layout(fig, height=max(300, min(620, 115 + 44 * max(len(rows), 3))))
    fig.update_layout(barmode="overlay")
    fig.update_xaxes(type="date", gridcolor=GRID, tickformat="%b\n%Y", rangeslider={"visible": True, "thickness": 0.08})
    fig.update_yaxes(
        categoryorder="array",
        categoryarray=list(reversed(rows)),
        automargin=True,
        gridcolor="rgba(0,0,0,0)",
    )
    return fig


def build_tax_free_donut(row: pd.Series) -> go.Figure:
    free = float(row["tax_free_units"])
    locked = float(row["locked_units"])
    total = float(row["total_units"])
    percentage = float(row["tax_free_pct"])
    values = [free, locked]
    if total <= 1e-9:
        values = [0, 1]

    fig = go.Figure(
        go.Pie(
            values=values,
            labels=["Tax-free now", "Still maturing"],
            hole=0.72,
            sort=False,
            direction="clockwise",
            marker={
                "colors": [row["color"], "rgba(96,111,143,0.22)"],
                "line": {"color": "rgba(255,255,255,0.08)", "width": 1},
            },
            textinfo="none",
            hovertemplate="%{label}<br>%{value:,.6f}<br>%{percent}<extra></extra>",
        )
    )
    fig.add_annotation(
        x=0.5,
        y=0.53,
        text=f"<b>{percentage:.0f}%</b>",
        showarrow=False,
        font={"size": 28, "color": TEXT},
    )
    unit_label = "units" if row["unit_kind"] == "units" else "€ proxy"
    fig.add_annotation(
        x=0.5,
        y=0.38,
        text=f"{free:,.4f} {unit_label}",
        showarrow=False,
        font={"size": 10, "color": MUTED},
    )
    fig.update_layout(
        height=245,
        paper_bgcolor=PAPER,
        plot_bgcolor=PAPER,
        font={"family": "Inter, ui-sans-serif, system-ui", "color": TEXT},
        margin={"l": 5, "r": 5, "t": 42, "b": 5},
        title={"text": row["asset_name"], "x": 0.5, "font": {"size": 14, "color": TEXT}},
        showlegend=False,
    )
    return fig


PLOTLY_CONFIG = {
    "displaylogo": False,
    "scrollZoom": True,
    "responsive": True,
    "modeBarButtonsToRemove": ["lasso2d", "select2d", "autoScale2d"],
}
