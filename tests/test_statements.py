import math

import pytest

from isviz import analysis
from isviz.statements import build_income_statement


def test_tag_drift_resolved_per_year(facts):
    s = build_income_statement(facts, "fix", years=10)
    assert list(s.data.index) == [2019, 2020, 2021, 2022, 2023]
    assert s.data.loc[2019, "revenue"] == 800
    assert s.sources["revenue"][2019] == "SalesRevenueNet"
    # Both tags report FY2020; the higher-priority ASC 606 concept wins.
    assert s.sources["revenue"][2020] == "RevenueFromContractWithCustomerExcludingAssessedTax"


def test_ignores_quarterly_and_stub_periods(facts):
    s = build_income_statement(facts, "fix")
    assert s.data.loc[2023, "revenue"] == 1210


def test_restatement_uses_latest_filing_and_is_flagged(facts):
    s = build_income_statement(facts, "fix")
    assert s.data.loc[2021, "net_income"] == 110
    assert s.restated == {"net_income": [2021]}


def test_gross_profit_derived_when_untagged(facts):
    s = build_income_statement(facts, "fix")
    assert s.data.loc[2023, "gross_profit"] == 1210 - 700
    assert s.sources["gross_profit"][2023].startswith("derived")


def test_years_limits_to_most_recent(facts):
    s = build_income_statement(facts, "fix", years=2)
    assert list(s.data.index) == [2022, 2023]
    assert set(s.period_end) == {2022, 2023}


def test_missing_revenue_raises(facts):
    for k in ("SalesRevenueNet", "RevenueFromContractWithCustomerExcludingAssessedTax"):
        del facts["facts"]["us-gaap"][k]
    with pytest.raises(ValueError, match="revenue"):
        build_income_statement(facts, "fix")


def test_ifrs_filer_raises():
    with pytest.raises(ValueError, match="IFRS"):
        build_income_statement({"facts": {"ifrs-full": {}}}, "fix")


def test_margins_and_growth(facts):
    s = build_income_statement(facts, "fix")
    m = analysis.margins(s)
    assert m.loc[2023, "gross_margin"] == pytest.approx(510 / 1210)
    assert m.loc[2023, "effective_tax_rate"] == pytest.approx(42 / 200)
    g = analysis.yoy_growth(s)
    assert g.loc[2023, "revenue"] == pytest.approx(0.10)
    # FY2021 net income grew off a loss year: growth is undefined, not a misleading number.
    assert math.isnan(g.loc[2021, "net_income"])


def test_cagr(facts):
    s = build_income_statement(facts, "fix")
    assert analysis.cagr(s, "revenue") == pytest.approx((1210 / 800) ** (1 / 4) - 1)
    assert analysis.cagr(s, "research_and_development") is None


def test_summary_is_json_safe(facts):
    import json

    snap = analysis.summary(build_income_statement(facts, "fix"))
    json.dumps(snap)  # no NaN / numpy types
    assert snap["latest"]["research_and_development"] is None
    assert snap["restated_items"] == {"net_income": [2021]}


def test_compare(facts):
    a = build_income_statement(facts, "aaa")
    b = build_income_statement(facts, "bbb", years=3)
    table = analysis.compare([a, b])
    assert list(table.index) == ["AAA", "BBB"]
    assert table.loc["AAA", "revenue"] == 1210
