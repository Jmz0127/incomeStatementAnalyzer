"""Ratio analysis on top of an IncomeStatement."""

from __future__ import annotations

import math

import pandas as pd

from isviz.statements import IncomeStatement

MARGINS = {
    "gross_margin": "gross_profit",
    "operating_margin": "operating_income",
    "pretax_margin": "pretax_income",
    "net_margin": "net_income",
}

GROWTH_ITEMS = ["revenue", "gross_profit", "operating_income", "net_income", "eps_diluted"]


def margins(stmt: IncomeStatement) -> pd.DataFrame:
    df = stmt.data
    out = pd.DataFrame(index=df.index)
    for name, item in MARGINS.items():
        out[name] = df[item] / df["revenue"]
    out["effective_tax_rate"] = df["income_tax"] / df["pretax_income"]
    out["rnd_intensity"] = df["research_and_development"] / df["revenue"]
    return out


def yoy_growth(stmt: IncomeStatement) -> pd.DataFrame:
    df = stmt.data[GROWTH_ITEMS]
    # Growth on a negative base is meaningless (a smaller loss isn't "-50% growth").
    prior = df.shift(1)
    growth = (df - prior) / prior.abs()
    return growth.where(prior > 0)


def cagr(stmt: IncomeStatement, item: str = "revenue") -> float | None:
    series = stmt.data[item].dropna()
    if len(series) < 2 or series.iloc[0] <= 0 or series.iloc[-1] <= 0:
        return None
    periods = int(series.index[-1]) - int(series.index[0])
    return float((series.iloc[-1] / series.iloc[0]) ** (1 / periods) - 1)


def common_size(stmt: IncomeStatement) -> pd.DataFrame:
    """Every dollar line as a % of revenue (EPS excluded)."""
    df = stmt.data.drop(columns=["eps_diluted"])
    return df.div(df["revenue"], axis=0)


def _clean(v: object) -> float | None:
    if v is None:
        return None
    f = float(v)  # type: ignore[arg-type]
    return None if math.isnan(f) else round(f, 4)


def summary(stmt: IncomeStatement) -> dict[str, object]:
    """Compact, JSON-friendly snapshot used by the CLI, MCP server, and narrative."""
    latest = int(stmt.data.index[-1])
    m = margins(stmt).loc[latest]
    g = yoy_growth(stmt).loc[latest]
    end = stmt.period_end.get(latest)
    return {
        "ticker": stmt.ticker,
        "company": stmt.company,
        "latest_fiscal_year": latest,
        "period_end": end.isoformat() if end else None,
        "years_covered": [int(y) for y in stmt.data.index],
        "latest": {k: _clean(v) for k, v in stmt.data.loc[latest].items()},
        "margins": {k: _clean(v) for k, v in m.items()},
        "yoy_growth": {k: _clean(v) for k, v in g.items()},
        "revenue_cagr": _clean(cagr(stmt, "revenue")),
        "net_income_cagr": _clean(cagr(stmt, "net_income")),
        "restated_items": stmt.restated,
    }


def compare(statements: list[IncomeStatement]) -> pd.DataFrame:
    """Peer table: one row per company, latest-year size, margins, growth."""
    rows = []
    for s in statements:
        latest = int(s.data.index[-1])
        rows.append(
            {
                "ticker": s.ticker,
                "fiscal_year": latest,
                "revenue": s.data.at[latest, "revenue"],
                "net_income": s.data.at[latest, "net_income"],
                **margins(s).loc[latest].to_dict(),
                "revenue_yoy": yoy_growth(s).at[latest, "revenue"],
                "revenue_cagr": cagr(s, "revenue"),
            }
        )
    return pd.DataFrame(rows).set_index("ticker")
