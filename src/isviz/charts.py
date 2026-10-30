"""Interactive Plotly charts."""

from __future__ import annotations

import plotly.graph_objects as go
from plotly.subplots import make_subplots

from isviz import analysis
from isviz.statements import IncomeStatement


def overview(stmt: IncomeStatement) -> go.Figure:
    """Revenue / gross profit / net income bars with margin lines on a second axis."""
    df = stmt.data
    years = [f"FY{y}" for y in df.index]
    m = analysis.margins(stmt)

    fig = make_subplots(specs=[[{"secondary_y": True}]])
    for item, name in [
        ("revenue", "Revenue"),
        ("gross_profit", "Gross profit"),
        ("net_income", "Net income"),
    ]:
        fig.add_bar(x=years, y=df[item] / 1e9, name=name, secondary_y=False)
    for col, name in [("gross_margin", "Gross margin"), ("net_margin", "Net margin")]:
        fig.add_scatter(x=years, y=m[col], name=name, mode="lines+markers", secondary_y=True)
    fig.update_layout(
        title=f"{stmt.company} ({stmt.ticker}) — income statement trend",
        barmode="group",
        legend={"orientation": "h", "y": -0.15},
        hovermode="x unified",
    )
    fig.update_yaxes(title_text="$ billions", tickprefix="$", secondary_y=False)
    fig.update_yaxes(title_text="Margin", tickformat=".0%", secondary_y=True, showgrid=False)
    return fig


def peer_margins(statements: list[IncomeStatement]) -> go.Figure:
    table = analysis.compare(statements)
    fig = go.Figure()
    for col, name in [
        ("gross_margin", "Gross"),
        ("operating_margin", "Operating"),
        ("net_margin", "Net"),
    ]:
        fig.add_bar(x=table.index, y=table[col], name=name)
    fig.update_layout(title="Latest fiscal year margins", barmode="group")
    fig.update_yaxes(tickformat=".0%")
    return fig
