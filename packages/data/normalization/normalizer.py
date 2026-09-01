"""Data normalization — PRD Section 4.3 step 3.

Normalizes identifiers, currency, calendar, and units.
"""

import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from packages.data.providers.base import Bar, InstrumentRecord

logger = logging.getLogger(__name__)

# Common exchange timezone mappings
_EXCHANGE_TIMEZONES = {
    "NYSE": "America/New_York",
    "NASDAQ": "America/New_York",
    "AMEX": "America/New_York",
    "LSE": "Europe/London",
    "TSE": "Asia/Tokyo",
    "HKEX": "Asia/Hong_Kong",
    "SIX": "Europe/Zurich",
    "ASX": "Australia/Sydney",
}


class DataNormalizer:
    """Normalizes market data to canonical form."""

    def __init__(self, target_currency: str = "USD"):
        self._target_currency = target_currency

    def normalize_symbol(self, symbol: str) -> str:
        """Normalize a symbol to uppercase, strip whitespace."""
        return symbol.strip().upper()

    def normalize_bar(self, bar: Bar) -> Bar:
        """Normalize a single bar to canonical form."""
        return Bar(
            symbol=self.normalize_symbol(bar.symbol),
            timeframe=bar.timeframe,
            ts_open=self._to_utc(bar.ts_open),
            ts_close=self._to_utc(bar.ts_close),
            open=self._round_price(bar.open),
            high=self._round_price(bar.high),
            low=self._round_price(bar.low),
            close=self._round_price(bar.close),
            volume=self._round_volume(bar.volume),
            vwap=self._round_price(bar.vwap) if bar.vwap else None,
            trade_count=bar.trade_count,
            currency=bar.currency.upper() if bar.currency else self._target_currency,
        )

    def normalize_instrument(self, instrument: InstrumentRecord) -> InstrumentRecord:
        """Normalize instrument metadata."""
        return InstrumentRecord(
            symbol=self.normalize_symbol(instrument.symbol),
            name=instrument.name.strip() if instrument.name else instrument.symbol,
            type=instrument.type,
            exchange=instrument.exchange.strip().upper() if instrument.exchange else None,
            currency=instrument.currency.upper() if instrument.currency else self._target_currency,
            isin=instrument.isin.strip().upper() if instrument.isin else None,
            cusip=instrument.cusip.strip().upper() if instrument.cusip else None,
            sector=instrument.sector.strip() if instrument.sector else None,
            industry=instrument.industry.strip() if instrument.industry else None,
            country=instrument.country.strip().upper() if instrument.country else None,
            metadata=instrument.metadata or {},
        )

    def _to_utc(self, dt: datetime) -> datetime:
        """Ensure datetime is UTC-aware."""
        if dt.tzinfo is None:
            # Assume UTC if no timezone
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)

    def _round_price(self, price: Optional[Decimal], decimals: int = 6) -> Optional[Decimal]:
        """Round price to consistent precision."""
        if price is None:
            return None
        return round(price, decimals)

    def _round_volume(self, volume: Decimal, decimals: int = 2) -> Decimal:
        """Round volume to consistent precision."""
        return round(volume, decimals)
