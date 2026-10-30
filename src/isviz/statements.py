"""Turn raw XBRL company facts into a clean annual income statement.

Three accounting realities this module handles:

1. Tag drift. Filers change which us-gaap concept they use for the same line
   (Apple moved from ``SalesRevenueNet`` to ``RevenueFromContractWithCustomer...``
   when ASC 606 took effect). Each line item lists candidate concepts in
   priority order and is resolved *per fiscal year*.
2. Comparatives and restatements. Every 10-K re-reports prior years. We key
   facts by period end date and keep the most recently filed value, and flag
   years whose value changed between filings.
3. Period noise. Company facts mix quarterly, year-to-date, and annual values.
   Only ~12-month durations from annual forms are kept.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any

import pandas as pd

ANNUAL_FORMS = {"10-K", "10-K/A", "10-KT", "20-F", "20-F/A", "40-F", "40-F/A"}

# line item -> candidate us-gaap concepts, highest priority first
LINE_ITEMS: dict[str, list[str]] = {
    "revenue": [
        "Revenues",
        "RevenueFromContractWithCustomerExcludingAssessedTax",
        "RevenueFromContractWithCustomerIncludingAssessedTax",
        "SalesRevenueNet",
        "SalesRevenueGoodsNet",
    ],
    "cost_of_revenue": [
        "CostOfRevenue",
        "CostOfGoodsAndServicesSold",
        "CostOfGoodsSold",
        "CostOfServices",
    ],
    "gross_profit": ["GrossProfit"],
    "research_and_development": ["ResearchAndDevelopmentExpense"],
    "selling_general_admin": ["SellingGeneralAndAdministrativeExpense"],
    "operating_expenses": ["OperatingExpenses"],
    "operating_income": ["OperatingIncomeLoss"],
    "pretax_income": [
        "IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest",
        "IncomeLossFromContinuingOperationsBeforeIncomeTaxesMinorityInterestAndIncomeLossFromEquityMethodInvestments",
    ],
    "income_tax": ["IncomeTaxExpenseBenefit"],
    "net_income": ["NetIncomeLoss", "ProfitLoss"],
    "eps_diluted": ["EarningsPerShareDiluted"],
}

LABELS: dict[str, str] = {
    "revenue": "Revenue",
    "cost_of_revenue": "Cost of revenue",
    "gross_profit": "Gross profit",
    "research_and_development": "Research & development",
    "selling_general_admin": "Selling, general & admin",
    "operating_expenses": "Total operating expenses",
    "operating_income": "Operating income",
    "pretax_income": "Pre-tax income",
    "income_tax": "Income tax expense",
    "net_income": "Net income",
    "eps_diluted": "Diluted EPS",
}


@dataclass
class IncomeStatement:
    ticker: str
    company: str
    cik: int
    data: pd.DataFrame  # index: fiscal year (int); columns: LINE_ITEMS keys
    period_end: dict[int, date] = field(default_factory=dict)
    sources: dict[str, dict[int, str]] = field(default_factory=dict)  # item -> year -> concept
    restated: dict[str, list[int]] = field(default_factory=dict)  # item -> years revised

    def labeled(self) -> pd.DataFrame:
        """Years as columns, human-readable line items as rows (statement layout)."""
        return self.data.T.rename(index=LABELS)


def _annual_facts(concept: dict[str, Any]) -> dict[date, tuple[float, bool]]:
    """Map period end -> (latest filed value, was_restated) for ~12-month periods."""
    units = concept.get("units", {})
    facts = units.get("USD") or units.get("USD/shares") or []
    by_end: dict[date, list[dict[str, Any]]] = {}
    for f in facts:
        if f.get("form") not in ANNUAL_FORMS or "start" not in f:
            continue
        start, end = date.fromisoformat(f["start"]), date.fromisoformat(f["end"])
        if not 350 <= (end - start).days <= 380:
            continue
        by_end.setdefault(end, []).append(f)

    out: dict[date, tuple[float, bool]] = {}
    for end, rows in by_end.items():
        rows.sort(key=lambda r: r["filed"])
        values = {r["val"] for r in rows}
        out[end] = (float(rows[-1]["val"]), len(values) > 1)
    return out


def build_income_statement(facts: dict[str, Any], ticker: str, years: int = 10) -> IncomeStatement:
    gaap = facts.get("facts", {}).get("us-gaap", {})
    if not gaap:
        raise ValueError(
            f"{ticker}: no us-gaap facts (IFRS filers such as many 20-F companies aren't supported)"
        )

    values: dict[str, dict[int, float]] = {}
    sources: dict[str, dict[int, str]] = {}
    restated: dict[str, list[int]] = {}
    period_end: dict[int, date] = {}

    for item, concepts in LINE_ITEMS.items():
        for concept in concepts:
            if concept not in gaap:
                continue
            for end, (val, was_restated) in _annual_facts(gaap[concept]).items():
                fy = end.year
                if fy in values.get(item, {}):
                    continue  # a higher-priority concept already covers this year
                values.setdefault(item, {})[fy] = val
                sources.setdefault(item, {})[fy] = concept
                period_end.setdefault(fy, end)
                if was_restated:
                    restated.setdefault(item, []).append(fy)

    if "revenue" not in values:
        raise ValueError(f"{ticker}: could not find annual revenue in XBRL facts")

    df = pd.DataFrame(values).sort_index()
    df = df.reindex(columns=list(LINE_ITEMS))
    df.index.name = "fiscal_year"

    # Derive gross profit where the filer doesn't tag it but reports both inputs.
    derived = df["revenue"] - df["cost_of_revenue"]
    missing_gp = df["gross_profit"].isna() & derived.notna()
    df.loc[missing_gp, "gross_profit"] = derived[missing_gp]
    for fy in df.index[missing_gp]:
        sources.setdefault("gross_profit", {})[int(fy)] = "derived: revenue - cost_of_revenue"

    # Only keep years with revenue, then the most recent N.
    df = df[df["revenue"].notna()].tail(years)
    kept = set(df.index)
    return IncomeStatement(
        ticker=ticker.upper(),
        company=facts.get("entityName", ticker.upper()),
        cik=int(facts.get("cik", 0)),
        data=df,
        period_end={fy: d for fy, d in period_end.items() if fy in kept},
        sources={k: {fy: c for fy, c in v.items() if fy in kept} for k, v in sources.items()},
        restated={
            k: sorted(y for y in v if y in kept) for k, v in restated.items() if kept & set(v)
        },
    )
