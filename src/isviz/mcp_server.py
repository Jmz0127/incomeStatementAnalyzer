"""MCP server so Claude (Desktop, Code, or any MCP client) can query financials as tools.

Run with `isviz-mcp` (stdio transport).
"""

from __future__ import annotations

from typing import Any

from dotenv import load_dotenv
from mcp.server.mcpserver import MCPServer

from isviz import analysis
from isviz.edgar import EdgarClient
from isviz.statements import LABELS, build_income_statement

load_dotenv()

server = MCPServer(
    name="isviz",
    instructions=(
        "Annual income statement data for US public companies, extracted from SEC EDGAR "
        "XBRL filings. Dollar amounts are in USD (not thousands); ratios are decimals "
        "(0.25 = 25%). Fiscal years are labeled by the calendar year of the period end."
    ),
)
_client: EdgarClient | None = None


def _load(ticker: str, years: int):  # type: ignore[no-untyped-def]
    global _client
    _client = _client or EdgarClient()
    return build_income_statement(_client.company_facts(ticker), ticker, max(2, min(years, 20)))


@server.tool()
def get_income_statement(ticker: str, years: int = 5) -> dict[str, Any]:
    """Annual income statement line items for a US-listed company, by fiscal year.

    Includes the XBRL concept used for each value and any years whose value was
    revised in a later filing.
    """
    stmt = _load(ticker, years)
    return {
        "ticker": stmt.ticker,
        "company": stmt.company,
        "line_items": {
            LABELS[item]: {str(fy): (None if v != v else v) for fy, v in stmt.data[item].items()}
            for item in stmt.data.columns
        },
        "period_end": {str(fy): d.isoformat() for fy, d in stmt.period_end.items()},
        "restated": stmt.restated,
    }


@server.tool()
def get_financial_summary(ticker: str, years: int = 5) -> dict[str, Any]:
    """Latest-year snapshot: key line items, margins, YoY growth, and CAGR."""
    return analysis.summary(_load(ticker, years))


@server.tool()
def compare_companies(tickers: list[str], years: int = 5) -> list[dict[str, Any]]:
    """Compare latest-year revenue, net income, margins, and growth across companies."""
    table = analysis.compare([_load(t, years) for t in tickers])
    return [
        {"ticker": str(t), **{str(k): (None if v != v else v) for k, v in row.items()}}
        for t, row in table.to_dict(orient="index").items()
    ]


def main() -> None:
    server.run()


if __name__ == "__main__":
    main()
