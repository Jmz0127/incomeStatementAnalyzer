"""Synthetic, hand-built XBRL fixture (no real company data).

"Fixture Corp" is designed to exercise the tricky cases:
- revenue tag drift: SalesRevenueNet (FY2019-2020) -> RevenueFromContract... (FY2020-2023)
- a restatement: FY2021 net income filed as 120, revised to 110 in a 10-K/A
- period noise: quarterly 10-Q facts and a 3-month fact inside a 10-K
- no GrossProfit tag, so gross profit must be derived
- a loss year (FY2020) so growth off a negative base is suppressed
"""

from __future__ import annotations

from typing import Any

import pytest

YEAR_ENDS = {
    2019: "2019-12-31",
    2020: "2020-12-31",
    2021: "2021-12-31",
    2022: "2022-12-31",
    2023: "2023-12-31",
}


def fact(
    fy: int, val: float, form: str = "10-K", filed: str | None = None, months: int = 12
) -> dict[str, Any]:
    end = YEAR_ENDS[fy]
    start = f"{fy}-01-01" if months == 12 else f"{fy}-10-01"
    return {
        "start": start,
        "end": end,
        "val": val,
        "form": form,
        "fy": fy,
        "fp": "FY",
        "filed": filed or f"{fy + 1}-02-15",
    }


def usd(*facts: dict[str, Any]) -> dict[str, Any]:
    return {"units": {"USD": list(facts)}}


@pytest.fixture
def facts() -> dict[str, Any]:
    gaap = {
        "SalesRevenueNet": usd(fact(2019, 800), fact(2020, 900)),
        "RevenueFromContractWithCustomerExcludingAssessedTax": usd(
            fact(2020, 900),
            fact(2021, 1000),
            fact(2022, 1100),
            fact(2023, 1210),
            fact(2023, 300, months=3),  # Q4 stub inside the 10-K: must be ignored
            {**fact(2023, 600), "form": "10-Q"},  # quarterly form: must be ignored
        ),
        "CostOfRevenue": usd(
            *(
                fact(fy, v)
                for fy, v in [(2019, 500), (2020, 560), (2021, 600), (2022, 650), (2023, 700)]
            )
        ),
        "OperatingIncomeLoss": usd(
            *(
                fact(fy, v)
                for fy, v in [(2019, 100), (2020, -20), (2021, 150), (2022, 180), (2023, 220)]
            )
        ),
        "IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest": usd(
            *(
                fact(fy, v)
                for fy, v in [(2019, 90), (2020, -30), (2021, 140), (2022, 170), (2023, 200)]
            )
        ),
        "IncomeTaxExpenseBenefit": usd(
            *(fact(fy, v) for fy, v in [(2019, 20), (2020, 0), (2021, 30), (2022, 35), (2023, 42)])
        ),
        "NetIncomeLoss": usd(
            fact(2019, 70),
            fact(2020, -30),
            fact(2021, 120, filed="2022-02-15"),
            fact(2021, 110, form="10-K/A", filed="2022-06-30"),  # restatement
            fact(2022, 135),
            fact(2023, 158),
        ),
        "EarningsPerShareDiluted": {
            "units": {
                "USD/shares": [fact(fy, v) for fy, v in [(2021, 1.10), (2022, 1.35), (2023, 1.58)]]
            }
        },
    }
    return {"cik": 1234567, "entityName": "Fixture Corp", "facts": {"us-gaap": gaap}}
