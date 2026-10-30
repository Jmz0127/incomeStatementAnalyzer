"""Command-line interface: `isviz --help`."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import pandas as pd
import typer
from dotenv import load_dotenv

from isviz import analysis
from isviz.edgar import EdgarClient, EdgarError
from isviz.statements import IncomeStatement, build_income_statement

load_dotenv()
app = typer.Typer(help="Income statement analysis for any SEC filer.", no_args_is_help=True)

Years = Annotated[int, typer.Option("--years", "-y", min=2, max=20, help="Fiscal years to pull.")]


def load(ticker: str, years: int) -> IncomeStatement:
    try:
        client = EdgarClient()
        return build_income_statement(client.company_facts(ticker), ticker, years)
    except (EdgarError, ValueError) as exc:
        typer.secho(str(exc), fg=typer.colors.RED, err=True)
        raise typer.Exit(1) from exc


def _fmt_statement(stmt: IncomeStatement) -> str:
    table = stmt.labeled().copy()
    table.columns = [f"FY{y}" for y in table.columns]
    is_eps = table.index == "Diluted EPS"
    body = (table[~is_eps] / 1e6).map(lambda v: "" if pd.isna(v) else f"{v:,.0f}")
    eps = table[is_eps].map(lambda v: "" if pd.isna(v) else f"{v:.2f}")
    return pd.concat([body, eps]).to_string()


@app.command()
def show(ticker: str, years: Years = 5, as_json: bool = typer.Option(False, "--json")) -> None:
    """Print the income statement ($ millions) and key ratios."""
    stmt = load(ticker, years)
    if as_json:
        typer.echo(json.dumps(analysis.summary(stmt), indent=2))
        return
    typer.secho(f"\n{stmt.company} ({stmt.ticker}) — $ millions except EPS\n", bold=True)
    typer.echo(_fmt_statement(stmt))
    snap = analysis.summary(stmt)
    margins = snap["margins"]
    typer.echo("")
    for key in ("gross_margin", "operating_margin", "net_margin", "effective_tax_rate"):
        val = margins[key]  # type: ignore[index]
        typer.echo(
            f"{key.replace('_', ' ').capitalize():<20} {'n/a' if val is None else f'{val:.1%}'}"
        )
    if snap["revenue_cagr"] is not None:
        typer.echo(f"{'Revenue CAGR':<20} {snap['revenue_cagr']:.1%}")
    if stmt.restated:
        typer.secho(f"\nRevised between filings: {stmt.restated}", fg=typer.colors.YELLOW)


@app.command()
def export(
    ticker: str,
    years: Years = 10,
    output: Annotated[Path | None, typer.Option("--output", "-o")] = None,
) -> None:
    """Write a formatted Excel workbook with ratios and an XBRL audit trail."""
    from isviz.export import to_excel

    stmt = load(ticker, years)
    path = to_excel(stmt, output or Path(f"{stmt.ticker}_income_statement.xlsx"))
    typer.secho(f"Wrote {path}", fg=typer.colors.GREEN)


@app.command()
def chart(
    ticker: str,
    years: Years = 10,
    output: Annotated[Path | None, typer.Option("--output", "-o")] = None,
) -> None:
    """Save an interactive HTML chart."""
    from isviz.charts import overview

    stmt = load(ticker, years)
    path = output or Path(f"{stmt.ticker}_chart.html")
    overview(stmt).write_html(path, include_plotlyjs="cdn")
    typer.secho(f"Wrote {path}", fg=typer.colors.GREEN)


@app.command()
def compare(tickers: list[str], years: Years = 5) -> None:
    """Side-by-side margins and growth for peer companies."""
    table = analysis.compare([load(t, years) for t in tickers])
    money = ["revenue", "net_income"]
    shown = table.copy().astype(object)
    shown[money] = table[money].map(lambda v: f"${v / 1e9:,.1f}B")
    pct_cols = [c for c in table.columns if c not in money + ["fiscal_year"]]
    shown[pct_cols] = table[pct_cols].map(lambda v: "n/a" if pd.isna(v) else f"{v:.1%}")
    typer.echo(shown.T.to_string())


@app.command()
def narrate(ticker: str, years: Years = 5) -> None:
    """Generate MD&A-style commentary with Claude (needs ANTHROPIC_API_KEY)."""
    from isviz.narrative import NarrativeError, generate

    stmt = load(ticker, years)
    try:
        typer.echo(generate(stmt))
    except NarrativeError as exc:
        typer.secho(str(exc), fg=typer.colors.RED, err=True)
        raise typer.Exit(1) from exc


if __name__ == "__main__":
    app()
