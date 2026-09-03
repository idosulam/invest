"""MarketDataProvider interface — PRD Section 4.1.

All data source adapters implement this protocol.
Supports licensed vendors, user-uploaded CSV/Parquet, and public regulatory data.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Iterable, Optional, Protocol

from packages.domain.enums.common import (
    CorporateActionType, DataQualityStatus, InstrumentType, Timeframe,
)


# ── Request/Response models ─────────────────────────────────

@dataclass
class InstrumentRecord:
    """Instrument metadata from a data provider."""
    symbol: str
    name: str
    type: InstrumentType
    exchange: Optional[str] = None
    currency: str = "USD"
    isin: Optional[str] = None
    cusip: Optional[str] = None
    sector: Optional[str] = None
    industry: Optional[str] = None
    country: Optional[str] = None
    metadata: dict = field(default_factory=dict)


@dataclass
class Bar:
    """A single OHLCV bar."""
    symbol: str
    timeframe: Timeframe
    ts_open: datetime
    ts_close: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal
    vwap: Optional[Decimal] = None
    trade_count: Optional[int] = None
    currency: str = "USD"


@dataclass
class CorporateActionRecord:
    """A corporate action (split, dividend, etc.)."""
    symbol: str
    type: CorporateActionType
    ex_date: datetime
    effective_date: Optional[datetime] = None
    record_date: Optional[datetime] = None
    factor: Optional[Decimal] = None
    cash_amount: Optional[Decimal] = None
    currency: str = "USD"
    description: Optional[str] = None


@dataclass
class FundamentalRecord:
    """A fundamental data point (revenue, P/E, etc.)."""
    symbol: str
    taxonomy: str
    period: str
    value: Decimal
    unit: str
    filed_date: Optional[datetime] = None
    accession: Optional[str] = None


@dataclass
class BarsRequest:
    """Request for bar data."""
    symbols: list[str]
    timeframe: Timeframe = Timeframe.DAILY
    start: Optional[datetime] = None
    end: Optional[datetime] = None


@dataclass
class ActionRequest:
    """Request for corporate actions."""
    symbols: list[str]
    start: Optional[datetime] = None
    end: Optional[datetime] = None


@dataclass
class FundamentalRequest:
    """Request for fundamental data."""
    symbols: list[str]
    taxonomy: Optional[str] = None
    period: Optional[str] = None


@dataclass
class NewsRecord:
    """A news article linked to a symbol, with sentiment."""
    symbol: str
    title: str
    summary: str
    source: str
    url: str
    published_at: datetime
    sentiment_score: Optional[Decimal] = None  # -1 (very bearish) to +1 (very bullish)
    sentiment_label: Optional[str] = None       # e.g. "Bullish", "Neutral", "Bearish"
    relevance_score: Optional[Decimal] = None   # 0 to 1, how relevant to this symbol


@dataclass
class NewsRequest:
    """Request for news articles."""
    symbols: list[str]
    limit: int = 20


@dataclass
class ProviderHealth:
    """Health status of a data provider."""
    name: str
    status: str  # "ok", "degraded", "down"
    last_successful_fetch: Optional[datetime] = None
    error_message: Optional[str] = None
    rate_limit_remaining: Optional[int] = None


# ── Protocol ────────────────────────────────────────────────

class MarketDataProvider(Protocol):
    """Interface that all data source adapters must implement."""

    @property
    def name(self) -> str:
        """Provider name for logging and identification."""
        ...

    def instruments(self) -> Iterable[InstrumentRecord]:
        """List available instruments from this provider."""
        ...

    def bars(self, request: BarsRequest) -> Iterable[Bar]:
        """Fetch OHLCV bars for the given symbols and time range."""
        ...

    def corporate_actions(self, request: ActionRequest) -> Iterable[CorporateActionRecord]:
        """Fetch corporate actions (splits, dividends, etc.)."""
        ...

    def fundamentals(self, request: FundamentalRequest) -> Iterable[FundamentalRecord]:
        """Fetch fundamental data points."""
        ...

    def health(self) -> ProviderHealth:
        """Check provider health and availability."""
        ...
