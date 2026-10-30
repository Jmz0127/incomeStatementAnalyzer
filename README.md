# Income Statement Analyzer (`isviz`)

[![CI](https://github.com/Jmz0127/incomeStatementAnalyzer/actions/workflows/ci.yml/badge.svg)](https://github.com/Jmz0127/incomeStatementAnalyzer/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/python-3.11%20%7C%203.12%20%7C%203.13-blue)
![License](https://img.shields.io/badge/license-MIT-green)

Pull annual income statements for any SEC filer straight from **EDGAR XBRL filings**, run margin, growth, and common-size analysis, export a **review-ready Excel workbook with an XBRL audit trail**, generate **MD&A-style commentary with Claude**, and expose all of it to AI assistants through an **MCP server**.

No paid data vendor or API key is needed for the data. It comes from the SEC.

```
$ isviz compare AAPL MSFT NVDA WMT -y 3
ticker                 AAPL     MSFT     NVDA      WMT
fiscal_year            2025     2026     2026     2026
revenue             $416.2B  $331.8B  $215.9B  $713.2B
gross_margin          46.9%    67.9%    71.1%    24.9%
operating_margin      32.0%    46.8%    60.4%     4.2%
net_margin            26.9%    40.3%    55.6%     3.1%
revenue_yoy            6.4%    17.8%    65.5%     4.7%
```

## Why XBRL, and what it takes to get it right

Financial statements filed with the SEC are tagged in XBRL, so the SEC's [company-facts API](https://www.sec.gov/search-filings/edgar-application-programming-interfaces) is the primary source behind every commercial data feed. Raw XBRL is messy, though, and `isviz` handles the problems an accountant would look for:

| Problem | Example | How it's handled |
|---|---|---|
| **Tag drift** | Apple reported revenue as `SalesRevenueNet` until ASC 606, then switched to `RevenueFromContractWithCustomerExcludingAssessedTax` | Each line item has ranked candidate concepts, resolved **per fiscal year** |
| **Comparatives & restatements** | Every 10-K re-reports two prior years; a 10-K/A may revise them | Facts are keyed by period end. The **latest filing wins**, and values that changed between filings are flagged (and highlighted in Excel) |
| **Period noise** | Company facts mix quarterly, YTD, and annual values | Only ~12-month durations from annual forms (10-K, 20-F, 40-F, amendments) are kept |
| **Missing subtotals** | Many filers don't tag `GrossProfit` | Derived as revenue − cost of revenue, labeled as derived in the audit trail |
| **Meaningless ratios** | "Growth" from a net loss to a profit | YoY growth on a negative base is reported as n/a, not a misleading percentage |

Every number in the Excel export can be traced to the XBRL concept it came from (see the **XBRL Sources** sheet).

## Quick start

```bash
git clone https://github.com/Jmz0127/incomeStatementAnalyzer && cd incomeStatementAnalyzer
uv venv && uv pip install -e ".[ai,mcp,app]"     # or: python -m venv .venv && pip install -e ".[ai,mcp,app]"
cp .env.example .env                               # set SEC_USER_AGENT (required by SEC) and optionally ANTHROPIC_API_KEY
```

### CLI

```bash
isviz show AAPL                      # statement ($M) + margins, tax rate, CAGR
isviz show AAPL --json               # machine-readable summary
isviz export MSFT -y 10              # MSFT_income_statement.xlsx
isviz chart NVDA                     # interactive HTML chart
isviz compare AAPL MSFT GOOGL        # peer table
isviz narrate AAPL                   # Claude-written MD&A-style commentary
```

### Web app

```bash
streamlit run app/streamlit_app.py
```

KPI cards, interactive Plotly charts, ratio tables, peer comparison, one-click Excel download, AI commentary, and the XBRL source map. You can deploy it free on [Streamlit Community Cloud](https://streamlit.io/cloud) by pointing it at `app/streamlit_app.py` and adding `SEC_USER_AGENT` (and optionally `ANTHROPIC_API_KEY`) as secrets.

### MCP server (use it from Claude)

`isviz-mcp` exposes three tools: `get_income_statement`, `get_financial_summary`, and `compare_companies`. Once it's set up, you can ask Claude things like *"Compare Costco's and Walmart's margin trends over the last five years."*

Claude Code:

```bash
claude mcp add isviz --env SEC_USER_AGENT="Your Name you@example.com" -- isviz-mcp
```

Claude Desktop (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "isviz": {
      "command": "/path/to/.venv/bin/isviz-mcp",
      "env": { "SEC_USER_AGENT": "Your Name you@example.com" }
    }
  }
}
```

## AI commentary

`isviz narrate` (and the app's **AI commentary** tab) sends Claude only the figures `isviz` has already computed, and the prompt tells it to use nothing else. That way every number in the commentary ties back to the workbook. The default model is `claude-opus-5-5`, which you can override with `ISVIZ_MODEL`. Server-side refusal fallback is enabled.

## Architecture

```
SEC EDGAR ──► edgar.py ──► statements.py ──► analysis.py ──┬──► cli.py           (Typer)
(XBRL JSON)   rate limit,  concept mapping,   margins, YoY,  ├──► export.py        (openpyxl)
              disk cache   restatements,      CAGR, common   ├──► charts.py        (Plotly)
                           period filtering   size, peers    ├──► narrative.py     (Claude API)
                                                             ├──► mcp_server.py    (MCP)
                                                             └──► app/streamlit_app.py
```

## Development

```bash
uv pip install -e ".[ai,mcp,dev]"
pytest -m "not network"     # offline suite on a synthetic XBRL fixture
pytest -m network           # live check against the SEC API (needs SEC_USER_AGENT)
ruff check . && ruff format --check . && mypy src
```

Tests run against a **hand-built, synthetic XBRL fixture** (`tests/conftest.py`) designed to exercise tag drift, restatements, period noise, derived subtotals, and loss years, so CI never depends on live data. CI runs on Python 3.11–3.13, and a weekly scheduled job smoke-tests the live SEC API.

## Limitations

- US GAAP filers only. IFRS filers (many 20-F companies) use the `ifrs-full` taxonomy and aren't mapped yet.
- Fiscal years are labeled by the calendar year in which the period ends. Retailers with January year-ends may label the same year differently in their own filings.
- Banks and insurers use different income statement structures, so some line items will be blank.

## License

MIT
