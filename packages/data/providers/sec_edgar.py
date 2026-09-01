"""SEC EDGAR connector — free public API for US filings and fundamentals.

Rate limit: 10 requests/second per SEC fair-access policy.
Requires a User-Agent header identifying the application.
"""

import logging
import time
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Iterable, Optional

import httpx

from packages.data.providers.base import (
    ActionRequest, BarsRequest, CorporateActionRecord,
    FundamentalRecord, FundamentalRequest, InstrumentRecord,
    ProviderHealth,
)
from packages.domain.enums.common import CorporateActionType, InstrumentType

logger = logging.getLogger(__name__)

BASE_URL = "https://efts.sec.gov/LATEST"
SUBMISSIONS_URL = "https://data.sec.gov/submissions"
COMPANY_FACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts"
RATE_LIMIT_DELAY = 0.11  # ~9 req/sec to stay under 10/sec limit


class SECEdgarProvider:
    """SEC EDGAR data provider — free, public API.

    Provides:
    - Company facts (financial fundamentals from XBRL filings)
    - Full-text search of filings
    - Company submissions (recent filings)

    Rate limited to ~10 requests/second per SEC fair-access policy.
    """

    def __init__(self, user_agent: str = "MarketPlatform/0.1 (dev@example.com)"):
        self._user_agent = user_agent
        self._headers = {"User-Agent": user_agent}
        self._last_request_time = 0.0

    @property
    def name(self) -> str:
        return "sec_edgar"

    def _rate_limit(self):
        """Enforce SEC rate limit."""
        elapsed = time.time() - self._last_request_time
        if elapsed < RATE_LIMIT_DELAY:
            time.sleep(RATE_LIMIT_DELAY - elapsed)
        self._last_request_time = time.time()

    def _get(self, url: str) -> Optional[dict]:
        """Make a rate-limited GET request to SEC EDGAR."""
        self._rate_limit()
        try:
            with httpx.Client(timeout=30) as client:
                resp = client.get(url, headers=self._headers)
                if resp.status_code == 200:
                    return resp.json()
                elif resp.status_code == 404:
                    logger.warning(f"SEC EDGAR 404: {url}")
                    return None
                else:
                    logger.error(f"SEC EDGAR error {resp.status_code}: {url}")
                    return None
        except Exception as e:
            logger.error(f"SEC EDGAR request failed: {e}")
            return None

    def _get_cik(self, symbol: str) -> Optional[str]:
        """Look up CIK number for a ticker symbol."""
        url = f"{SUBMISSIONS_URL}/CIK{symbol.zfill(10)}.json"
        # Try the company tickers endpoint first
        tickers_url = "https://www.sec.gov/files/company_tickers.json"
        self._rate_limit()
        try:
            with httpx.Client(timeout=30) as client:
                resp = client.get(tickers_url, headers=self._headers)
                if resp.status_code == 200:
                    data = resp.json()
                    for _, entry in data.items():
                        if entry.get("ticker", "").upper() == symbol.upper():
                            return str(entry.get("cik_str", "")).zfill(10)
        except Exception as e:
            logger.error(f"Error looking up CIK for {symbol}: {e}")
        return None

    def instruments(self) -> Iterable[InstrumentRecord]:
        """List all SEC-registered companies (limited — use specific lookups)."""
        logger.info("SEC EDGAR: Use specific symbol lookups rather than full listing")
        return []

    def bars(self, request: BarsRequest) -> Iterable:
        """SEC EDGAR does not provide market data (bars/prices)."""
        logger.warning("SEC EDGAR does not provide OHLCV bar data")
        return []

    def corporate_actions(self, request: ActionRequest) -> Iterable[CorporateActionRecord]:
        """Fetch corporate actions from SEC 8-K filings.
        
        Note: SEC doesn't have a direct corporate actions API.
        This parses 8-K filings for material events.
        """
        for symbol in request.symbols:
            cik = self._get_cik(symbol)
            if not cik:
                logger.warning(f"CIK not found for {symbol}")
                continue

            url = f"{SUBMISSIONS_URL}/CIK{cik}.json"
            data = self._get(url)
            if not data:
                continue

            recent = data.get("filings", {}).get("recent", {})
            forms = recent.get("form", [])
            dates = recent.get("filingDate", [])
            accessions = recent.get("accessionNumber", [])

            for i, form in enumerate(forms):
                if form in ("8-K", "8-K/A"):
                    filing_date = dates[i] if i < len(dates) else None
                    if filing_date:
                        try:
                            dt = datetime.strptime(filing_date, "%Y-%m-%d")
                            if request.start and dt < request.start:
                                continue
                            if request.end and dt > request.end:
                                continue
                            # We flag 8-K filings as potential corporate actions
                            # The actual parsing of 8-K content would be more complex
                            yield CorporateActionRecord(
                                symbol=symbol,
                                type=CorporateActionType.LISTING,  # Generic event
                                ex_date=dt,
                                description=f"8-K filing: {form}",
                            )
                        except ValueError:
                            pass

    def fundamentals(self, request: FundamentalRequest) -> Iterable[FundamentalRecord]:
        """Fetch XBRL-tagged financial facts from SEC EDGAR companyfacts API."""
        for symbol in request.symbols:
            cik = self._get_cik(symbol)
            if not cik:
                logger.warning(f"CIK not found for {symbol}")
                continue

            url = f"{COMPANY_FACTS}/CIK{cik}.json"
            data = self._get(url)
            if not data:
                continue

            facts = data.get("facts", {})

            # Process US-GAAP facts
            us_gaap = facts.get("us-gaap", {})
            taxonomy_map = {
                "Revenues": ("revenue", "USD"),
                "RevenueFromContractWithCustomerExcludingAssessedTax": ("revenue", "USD"),
                "NetIncomeLoss": ("net_income", "USD"),
                "EarningsPerShareBasic": ("eps_basic", "USD"),
                "EarningsPerShareDiluted": ("eps_diluted", "USD"),
                "Assets": ("total_assets", "USD"),
                "Liabilities": ("total_liabilities", "USD"),
                "StockholdersEquity": ("stockholders_equity", "USD"),
                "OperatingIncomeLoss": ("operating_income", "USD"),
                "GrossProfit": ("gross_profit", "USD"),
                "CashAndCashEquivalentsAtCarryingValue": ("cash", "USD"),
                "LongTermDebt": ("long_term_debt", "USD"),
                "CommonStockSharesOutstanding": ("shares_outstanding", "shares"),
                "DividendsCommonStock": ("dividends", "USD"),
            }

            for xbrl_tag, (taxonomy, unit) in taxonomy_map.items():
                tag_data = us_gaap.get(xbrl_tag)
                if not tag_data:
                    continue

                units = tag_data.get("units", {})
                # Get the most common unit
                for unit_key, entries in units.items():
                    if not entries:
                        continue

                    # Get the latest entry
                    for entry in sorted(entries, key=lambda x: x.get("end", ""), reverse=True):
                        end_date = entry.get("end", "")
                        filed = entry.get("filed", "")
                        value = entry.get("val")
                        accn = entry.get("accn", "")

                        if value is None:
                            continue

                        # Filter by period if specified
                        if request.period and request.period not in end_date:
                            continue

                        try:
                            yield FundamentalRecord(
                                symbol=symbol,
                                taxonomy=taxonomy,
                                period=end_date,
                                value=Decimal(str(value)),
                                unit=unit,
                                filed_date=datetime.strptime(filed, "%Y-%m-%d") if filed else None,
                                accession=accn,
                            )
                            break  # Only latest per tag
                        except (InvalidOperation, ValueError):
                            continue

    def health(self) -> ProviderHealth:
        """Check SEC EDGAR API availability."""
        try:
            self._rate_limit()
            with httpx.Client(timeout=10) as client:
                resp = client.get(
                    "https://www.sec.gov/files/company_tickers.json",
                    headers=self._headers,
                )
                if resp.status_code == 200:
                    return ProviderHealth(
                        name=self.name,
                        status="ok",
                        last_successful_fetch=datetime.utcnow(),
                    )
                return ProviderHealth(
                    name=self.name,
                    status="degraded",
                    error_message=f"HTTP {resp.status_code}",
                )
        except Exception as e:
            return ProviderHealth(name=self.name, status="down", error_message=str(e))
