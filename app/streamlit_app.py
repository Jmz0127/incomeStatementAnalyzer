"""Streamlit front end: `streamlit run app/streamlit_app.py`."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

from isviz import analysis
from isviz.charts import overview, peer_margins
from isviz.edgar import EdgarClient, EdgarError
from isviz.export import to_excel
from isviz.statements import IncomeStatement, build_income_statement

load_dotenv()
# Streamlit Community Cloud exposes secrets via st.secrets; mirror them into env vars.
for key in ("SEC_USER_AGENT", "ANTHROPIC_API_KEY"):
    try:
        if key not in os.environ and key in st.secrets:
            os.environ[key] = st.secrets[key]
    except Exception:  # no secrets.toml locally
        break

st.set_page_config(page_title="Income Statement Analyzer", layout="wide")


@st.cache_data(ttl=60 * 60, show_spinner="Pulling XBRL data from SEC EDGAR…")
def load(ticker: str, years: int) -> IncomeStatement:
    return build_income_statement(EdgarClient().company_facts(ticker), ticker, years)


st.title("Income Statement Analyzer")
st.caption("Annual figures pulled directly from SEC EDGAR XBRL filings. No API key needed.")

with st.sidebar:
    ticker = st.text_input("Ticker", "AAPL").strip().upper()
    years = st.slider("Fiscal years", 3, 15, 10)
    peers_raw = st.text_input("Compare with (comma-separated)", "MSFT, GOOGL")

try:
    stmt = load(ticker, years)
except (EdgarError, ValueError) as exc:
    st.error(str(exc))
    st.stop()

snap = analysis.summary(stmt)
latest = snap["latest"]
margins = snap["margins"]
growth = snap["yoy_growth"]
st.subheader(f"{stmt.company} · FY{snap['latest_fiscal_year']} (period ended {snap['period_end']})")


def pct(v: object) -> str:
    return "n/a" if v is None else f"{v:.1%}"


c1, c2, c3, c4 = st.columns(4)
c1.metric("Revenue", f"${latest['revenue'] / 1e9:,.1f}B", pct(growth["revenue"]))  # type: ignore[index]
c2.metric("Gross margin", pct(margins["gross_margin"]))  # type: ignore[index]
c3.metric("Operating margin", pct(margins["operating_margin"]))  # type: ignore[index]
c4.metric("Net income", f"${latest['net_income'] / 1e9:,.1f}B", pct(growth["net_income"]))  # type: ignore[index]

st.plotly_chart(overview(stmt), width="stretch")

tab_is, tab_ratios, tab_peers, tab_ai, tab_src = st.tabs(
    ["Income statement", "Ratios", "Peers", "AI commentary", "XBRL sources"]
)

with tab_is:
    table = stmt.labeled() / 1e6
    table.loc["Diluted EPS"] *= 1e6
    table.columns = [f"FY{y}" for y in table.columns]
    st.caption("$ millions except EPS")
    st.dataframe(table.style.format("{:,.2f}", na_rep="–"), width="stretch")
    if stmt.restated:
        st.info(f"Values revised between filings: {stmt.restated}")
    with tempfile.TemporaryDirectory() as tmp:
        path = to_excel(stmt, Path(tmp) / f"{stmt.ticker}_income_statement.xlsx")
        st.download_button("Download Excel workbook", path.read_bytes(), file_name=path.name)

with tab_ratios:
    m = analysis.margins(stmt)
    m.index = [f"FY{y}" for y in m.index]
    st.dataframe(m.T.style.format("{:.1%}", na_rep="–"), width="stretch")
    g = analysis.yoy_growth(stmt)
    g.index = [f"FY{y}" for y in g.index]
    st.markdown("**Year-over-year growth**")
    st.dataframe(g.T.style.format("{:.1%}", na_rep="–"), width="stretch")

with tab_peers:
    peers = [p.strip().upper() for p in peers_raw.split(",") if p.strip()]
    statements = [stmt]
    for p in peers:
        try:
            statements.append(load(p, years))
        except (EdgarError, ValueError) as exc:
            st.warning(f"{p}: {exc}")
    st.plotly_chart(peer_margins(statements), width="stretch")
    peer_table = analysis.compare(statements)
    st.dataframe(
        peer_table.style.format(
            {
                c: "{:.1%}"
                for c in peer_table.columns
                if c not in ("fiscal_year", "revenue", "net_income")
            }
            | {"revenue": "${:,.0f}", "net_income": "${:,.0f}"},
            na_rep="–",
        ),
        width="stretch",
    )

with tab_ai:
    if not os.environ.get("ANTHROPIC_API_KEY"):
        st.info("Set ANTHROPIC_API_KEY to enable Claude-generated commentary.")
    elif st.button("Generate commentary"):
        from isviz.narrative import NarrativeError, generate

        with st.spinner("Claude is reading the numbers…"):
            try:
                st.markdown(generate(stmt))
            except NarrativeError as exc:
                st.error(str(exc))

with tab_src:
    rows = [
        {"line item": item, "fiscal year": fy, "XBRL concept": concept}
        for item, by_year in stmt.sources.items()
        for fy, concept in by_year.items()
    ]
    st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)
