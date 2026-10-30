"""Thin client for the SEC EDGAR XBRL APIs (free, no API key).

SEC fair-access policy requires a descriptive User-Agent with contact info and
caps traffic at 10 requests/second. Responses are cached on disk so repeated
runs don't re-download multi-megabyte company-facts files.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

import requests

TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
FACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json"
DEFAULT_CACHE_DIR = Path(os.environ.get("ISVIZ_CACHE_DIR", Path.home() / ".cache" / "isviz"))
CACHE_TTL_SECONDS = 24 * 60 * 60
MIN_REQUEST_INTERVAL = 0.11  # stay under SEC's 10 req/s limit


class EdgarError(RuntimeError):
    """Raised when EDGAR data can't be retrieved or a ticker can't be resolved."""


class EdgarClient:
    def __init__(
        self,
        user_agent: str | None = None,
        cache_dir: Path | None = DEFAULT_CACHE_DIR,
        session: requests.Session | None = None,
    ) -> None:
        user_agent = user_agent or os.environ.get("SEC_USER_AGENT")
        if not user_agent:
            raise EdgarError(
                "SEC requires a User-Agent with contact info. "
                'Set SEC_USER_AGENT="Your Name you@example.com" (see .env.example).'
            )
        self.session = session or requests.Session()
        self.session.headers.update({"User-Agent": user_agent, "Accept-Encoding": "gzip"})
        self.cache_dir = cache_dir
        self._last_request = 0.0
        self._tickers: dict[str, dict[str, Any]] | None = None

    def _get_json(self, url: str, cache_key: str) -> Any:
        cache_file = self.cache_dir / f"{cache_key}.json" if self.cache_dir else None
        is_fresh = (
            cache_file is not None
            and cache_file.exists()
            and time.time() - cache_file.stat().st_mtime < CACHE_TTL_SECONDS
        )
        if cache_file is not None and is_fresh:
            return json.loads(cache_file.read_text())

        wait = MIN_REQUEST_INTERVAL - (time.monotonic() - self._last_request)
        if wait > 0:
            time.sleep(wait)
        try:
            resp = self.session.get(url, timeout=30)
        except requests.RequestException as exc:
            raise EdgarError(f"Network error fetching {url}: {exc}") from exc
        finally:
            self._last_request = time.monotonic()

        if resp.status_code == 404:
            raise EdgarError(f"No XBRL data found at {url}")
        if resp.status_code != 200:
            raise EdgarError(f"SEC returned HTTP {resp.status_code} for {url}")
        data = resp.json()

        if cache_file:
            cache_file.parent.mkdir(parents=True, exist_ok=True)
            cache_file.write_text(json.dumps(data))
        return data

    def lookup(self, ticker: str) -> dict[str, Any]:
        """Return {"cik": int, "ticker": str, "title": str} for a ticker."""
        if self._tickers is None:
            raw = self._get_json(TICKERS_URL, "company_tickers")
            self._tickers = {row["ticker"].upper(): row for row in raw.values()}
        row = self._tickers.get(ticker.strip().upper().replace(".", "-"))
        if row is None:
            raise EdgarError(f"Ticker {ticker!r} not found in SEC's ticker list")
        return {"cik": int(row["cik_str"]), "ticker": row["ticker"], "title": row["title"]}

    def company_facts(self, ticker: str) -> dict[str, Any]:
        """Return the full XBRL company-facts document for a ticker."""
        cik = self.lookup(ticker)["cik"]
        return self._get_json(FACTS_URL.format(cik=cik), f"facts_{cik:010d}")
