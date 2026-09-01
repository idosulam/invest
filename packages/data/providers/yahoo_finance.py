"""Yahoo Finance adapter — free, development use only.

Uses yfinance library. Per Qlib's warning: Yahoo-derived data may be
imperfect; users should prepare higher-quality data for production.
"""

import logging
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Iterable, Optional

import yfinance as yf

from packages.data.providers.base import (
    ActionRequest, Bar, BarsRequest, CorporateActionRecord,
    FundamentalRecord, FundamentalRequest, InstrumentRecord,
    MarketDataProvider, ProviderHealth,
)
from packages.domain.enums.common import CorporateActionType, InstrumentType, Timeframe

logger = logging.getLogger(__name__)

# Map yfinance instrument types to our types
_TYPE_MAP = {
    "equity": InstrumentType.STOCK,
    "ETF": InstrumentType.ETF,
    "INDEX": InstrumentType.BENCHMARK,
    "mutualfund": InstrumentType.STOCK,
}


class YahooFinanceProvider:
    """Yahoo Finance data provider — free, no API key required.

    WARNING: For development and research only. Yahoo data may contain
    inaccuracies, survivorship bias, and adjusted-price inconsistencies.
    Use licensed data for production.
    """

    def __init__(self, max_symbols_per_batch: int = 50):
        self._max_batch = max_symbols_per_batch

    @property
    def name(self) -> str:
        return "yahoo_finance"

    def instruments(self) -> Iterable[InstrumentRecord]:
        """Not directly supported — Yahoo doesn't list all instruments.
        Use specific symbol lookups instead."""
        logger.warning("Yahoo Finance does not support bulk instrument listing")
        return []

    def bars(self, request: BarsRequest) -> Iterable[Bar]:
        """Fetch OHLCV bars from Yahoo Finance."""
        timeframe_map = {
            Timeframe.DAILY: "1d",
            Timeframe.HOURLY: "1h",
            Timeframe.MINUTE_15: "15m",
            Timeframe.MINUTE_5: "5m",
            Timeframe.MINUTE_1: "1m",
        }
        yf_interval = timeframe_map.get(request.timeframe, "1d")

        # Yahoo limits: 1m/2m/5m/15m max 7 days, 1h max 730 days
        end = request.end or datetime.utcnow()
        start = request.start or (end - timedelta(days=365))

        for i in range(0, len(request.symbols), self._max_batch):
            batch = request.symbols[i : i + self._max_batch]
            try:
                tickers = yf.Tickers(" ".join(batch))
                for symbol in batch:
                    try:
                        ticker = tickers.tickers.get(symbol) or yf.Ticker(symbol)
                        df = ticker.history(
                            start=start.strftime("%Y-%m-%d"),
                            end=end.strftime("%Y-%m-%d"),
                            interval=yf_interval,
                            auto_adjust=False,
                        )
                        if df.empty:
                            logger.warning(f"No data returned for {symbol}")
                            continue

                        for idx, row in df.iterrows():
                            try:
                                ts = idx.to_pydatetime()
                                yield Bar(
                                    symbol=symbol,
                                    timeframe=request.timeframe,
                                    ts_open=ts,
                                    ts_close=ts,
                                    open=Decimal(str(row["Open"])),
                                    high=Decimal(str(row["High"])),
                                    low=Decimal(str(row["Low"])),
                                    close=Decimal(str(row["Close"])),
                                    volume=Decimal(str(row["Volume"])),
                                    vwap=None,
                                    trade_count=None,
                                )
                            except (InvalidOperation, KeyError, ValueError) as e:
                                logger.warning(f"Skipping bar for {symbol} at {idx}: {e}")
                    except Exception as e:
                        logger.error(f"Error fetching bars for {symbol}: {e}")
            except Exception as e:
                logger.error(f"Error in batch fetch: {e}")

    def corporate_actions(self, request: ActionRequest) -> Iterable[CorporateActionRecord]:
        """Fetch splits and dividends from Yahoo Finance."""
        for symbol in request.symbols:
            try:
                ticker = yf.Ticker(symbol)

                # Dividends
                dividends = ticker.dividends
                if dividends is not None and not dividends.empty:
                    for ts, amount in dividends.items():
                        dt = ts.to_pydatetime()
                        if request.start and dt < request.start:
                            continue
                        if request.end and dt > request.end:
                            continue
                        yield CorporateActionRecord(
                            symbol=symbol,
                            type=CorporateActionType.DIVIDEND,
                            ex_date=dt,
                            cash_amount=Decimal(str(amount)),
                            description=f"Dividend ${amount}",
                        )

                # Splits
                splits = ticker.splits
                if splits is not None and not splits.empty:
                    for ts, ratio in splits.items():
                        dt = ts.to_pydatetime()
                        if request.start and dt < request.start:
                            continue
                        if request.end and dt > request.end:
                            continue
                        yield CorporateActionRecord(
                            symbol=symbol,
                            type=CorporateActionType.SPLIT,
                            ex_date=dt,
                            factor=Decimal(str(ratio)),
                            description=f"Split {ratio}:1",
                        )
            except Exception as e:
                logger.error(f"Error fetching corporate actions for {symbol}: {e}")

    def fundamentals(self, request: FundamentalRequest) -> Iterable[FundamentalRecord]:
        """Fetch basic fundamentals from Yahoo Finance info."""
        for symbol in request.symbols:
            try:
                ticker = yf.Ticker(symbol)
                info = ticker.info or {}

                # Map common fields
                field_map = {
                    "market_cap": ("market_capitalization", "USD"),
                    "trailing_pe": ("pe_ratio_ttm", "ratio"),
                    "forward_pe": ("pe_ratio_forward", "ratio"),
                    "price_to_book": ("price_to_book", "ratio"),
                    "dividend_yield": ("dividend_yield", "ratio"),
                    "beta": ("beta", "ratio"),
                    "trailing_eps": ("eps_ttm", "USD"),
                    "forward_eps": ("eps_forward", "USD"),
                    "revenue": ("revenue", "USD"),
                    "totalRevenue": ("revenue", "USD"),
                    "profitMargins": ("profit_margin", "ratio"),
                    "operatingMargins": ("operating_margin", "ratio"),
                    "returnOnEquity": ("roe", "ratio"),
                    "debtToEquity": ("debt_to_equity", "ratio"),
                    "currentRatio": ("current_ratio", "ratio"),
                    "52WeekChange": ("price_52w_change", "ratio"),
                }

                for yf_key, (taxonomy, unit) in field_map.items():
                    value = info.get(yf_key)
                    if value is not None:
                        try:
                            yield FundamentalRecord(
                                symbol=symbol,
                                taxonomy=taxonomy,
                                period="latest",
                                value=Decimal(str(value)),
                                unit=unit,
                            )
                        except (InvalidOperation, ValueError):
                            pass
            except Exception as e:
                logger.error(f"Error fetching fundamentals for {symbol}: {e}")

    def health(self) -> ProviderHealth:
        """Check Yahoo Finance availability."""
        try:
            ticker = yf.Ticker("AAPL")
            hist = ticker.history(period="1d")
            if hist.empty:
                return ProviderHealth(
                    name=self.name,
                    status="degraded",
                    error_message="No data returned for test query",
                )
            return ProviderHealth(
                name=self.name,
                status="ok",
                last_successful_fetch=datetime.utcnow(),
            )
        except Exception as e:
            return ProviderHealth(
                name=self.name,
                status="down",
                error_message=str(e),
            )

    def get_instrument_info(self, symbol: str) -> Optional[InstrumentRecord]:
        """Look up a single instrument's metadata."""
        try:
            ticker = yf.Ticker(symbol)
            info = ticker.info or {}
            if not info.get("symbol"):
                return None

            instrument_type = _TYPE_MAP.get(info.get("quoteType", ""), InstrumentType.STOCK)

            return InstrumentRecord(
                symbol=info.get("symbol", symbol),
                name=info.get("shortName") or info.get("longName", symbol),
                type=instrument_type,
                exchange=info.get("exchange"),
                currency=info.get("currency", "USD"),
                sector=info.get("sector"),
                industry=info.get("industry"),
                country=info.get("country"),
                metadata={
                    "yahoo_symbol": symbol,
                    "full_exchange": info.get("fullExchangeName"),
                    "market": info.get("market"),
                },
            )
        except Exception as e:
            logger.error(f"Error looking up {symbol}: {e}")
            return None
