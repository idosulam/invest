"""CSV/Parquet import adapter — for user-uploaded data files.

Supports flexible column mapping for common OHLCV formats.
"""

import csv
import logging
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Iterable, Optional

from packages.data.providers.base import (
    ActionRequest, Bar, BarsRequest, CorporateActionRecord,
    FundamentalRecord, FundamentalRequest, InstrumentRecord,
    ProviderHealth,
)
from packages.domain.enums.common import Timeframe

logger = logging.getLogger(__name__)

# Common column name aliases
_DEFAULT_COLUMN_MAP = {
    "date": "date",
    "timestamp": "date",
    "datetime": "date",
    "time": "date",
    "open": "open",
    "o": "open",
    "high": "high",
    "h": "high",
    "low": "low",
    "l": "low",
    "close": "close",
    "c": "close",
    "adj_close": "adj_close",
    "adj close": "adj_close",
    "adjusted_close": "adj_close",
    "volume": "volume",
    "vol": "volume",
    "v": "volume",
    "vwap": "vwap",
    "trade_count": "trade_count",
    "trades": "trade_count",
}


def _normalize_column(name: str) -> str:
    """Normalize a column name to our standard field name."""
    return _DEFAULT_COLUMN_MAP.get(name.strip().lower(), name.strip().lower())


def _parse_decimal(value: str) -> Optional[Decimal]:
    """Safely parse a decimal value."""
    if not value or value.strip() in ("", "null", "None", "N/A", "NA", "-"):
        return None
    try:
        return Decimal(value.strip().replace(",", ""))
    except (InvalidOperation, ValueError):
        return None


def _parse_date(value: str) -> Optional[datetime]:
    """Parse a date string in common formats."""
    formats = [
        "%Y-%m-%d",
        "%Y-%m-%d %H:%M:%S",
        "%Y/%m/%d",
        "%m/%d/%Y",
        "%d/%m/%Y",
        "%Y%m%d",
    ]
    value = value.strip()
    for fmt in formats:
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    return None


class CSVParquetProvider:
    """Import OHLCV data from CSV or Parquet files.

    Supports flexible column mapping — the adapter auto-detects
    common column names (Date, Open, High, Low, Close, Volume).
    """

    def __init__(
        self,
        file_path: str,
        symbol: Optional[str] = None,
        timeframe: Timeframe = Timeframe.DAILY,
        column_map: Optional[dict[str, str]] = None,
        date_format: Optional[str] = None,
    ):
        self._path = Path(file_path)
        self._symbol = symbol or self._path.stem.upper()
        self._timeframe = timeframe
        self._column_map = column_map or {}
        self._date_format = date_format

        if not self._path.exists():
            raise FileNotFoundError(f"Data file not found: {file_path}")

    @property
    def name(self) -> str:
        return f"csv_parquet_{self._path.name}"

    def instruments(self) -> Iterable[InstrumentRecord]:
        """Return the instrument implied by the file."""
        yield InstrumentRecord(
            symbol=self._symbol,
            name=self._symbol,
            type=__import__("packages.domain.enums.common", fromlist=["InstrumentType"]).InstrumentType.STOCK,
        )

    def bars(self, request: BarsRequest) -> Iterable[Bar]:
        """Read bars from CSV or Parquet file."""
        if self._path.suffix.lower() == ".parquet":
            yield from self._read_parquet(request)
        else:
            yield from self._read_csv(request)

    def _read_csv(self, request: BarsRequest) -> Iterable[Bar]:
        """Read bars from a CSV file."""
        with open(self._path, newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            # Normalize column names
            if reader.fieldnames:
                normalized_fields = {col: _normalize_column(col) for col in reader.fieldnames}
            else:
                return

            for row in reader:
                # Map to normalized names
                normalized = {}
                for orig_col, norm_col in normalized_fields.items():
                    normalized[norm_col] = row.get(orig_col, "")

                # Apply user column map overrides
                for user_col, target in self._column_map.items():
                    if user_col in normalized:
                        normalized[target] = normalized.pop(user_col)

                # Parse date
                date_str = normalized.get("date", "")
                if self._date_format:
                    try:
                        ts = datetime.strptime(date_str, self._date_format)
                    except ValueError:
                        continue
                else:
                    ts = _parse_date(date_str)
                    if ts is None:
                        continue

                # Filter by date range
                if request.start and ts < request.start:
                    continue
                if request.end and ts > request.end:
                    continue

                # Parse OHLCV
                open_ = _parse_decimal(normalized.get("open", ""))
                high = _parse_decimal(normalized.get("high", ""))
                low = _parse_decimal(normalized.get("low", ""))
                close = _parse_decimal(normalized.get("close", ""))
                volume = _parse_decimal(normalized.get("volume", ""))

                if all(v is not None for v in [open_, high, low, close, volume]):
                    yield Bar(
                        symbol=request.symbols[0] if request.symbols else self._symbol,
                        timeframe=self._timeframe,
                        ts_open=ts,
                        ts_close=ts,
                        open=open_,
                        high=high,
                        low=low,
                        close=close,
                        volume=volume,
                        vwap=_parse_decimal(normalized.get("vwap", "")),
                        trade_count=int(v) if (v := _parse_decimal(normalized.get("trade_count", ""))) else None,
                    )

    def _read_parquet(self, request: BarsRequest) -> Iterable[Bar]:
        """Read bars from a Parquet file."""
        try:
            import pyarrow.parquet as pq
            import pandas as pd
        except ImportError:
            logger.error("pyarrow and pandas required for Parquet import")
            return

        try:
            df = pq.read_table(self._path).to_pandas()
        except Exception as e:
            logger.error(f"Error reading Parquet file: {e}")
            return

        # Normalize column names
        df.columns = [_normalize_column(c) for c in df.columns]

        # Apply user column map
        df = df.rename(columns=self._column_map)

        for _, row in df.iterrows():
            ts = pd.Timestamp(row.get("date")).to_pydatetime()

            if request.start and ts < request.start:
                continue
            if request.end and ts > request.end:
                continue

            try:
                yield Bar(
                    symbol=request.symbols[0] if request.symbols else self._symbol,
                    timeframe=self._timeframe,
                    ts_open=ts,
                    ts_close=ts,
                    open=Decimal(str(row["open"])),
                    high=Decimal(str(row["high"])),
                    low=Decimal(str(row["low"])),
                    close=Decimal(str(row["close"])),
                    volume=Decimal(str(row.get("volume", 0))),
                    vwap=Decimal(str(row["vwap"])) if "vwap" in row and pd.notna(row.get("vwap")) else None,
                )
            except (InvalidOperation, KeyError, ValueError) as e:
                logger.warning(f"Skipping row at {ts}: {e}")

    def corporate_actions(self, request: ActionRequest) -> Iterable[CorporateActionRecord]:
        """Not supported for CSV/Parquet import."""
        return []

    def fundamentals(self, request: FundamentalRequest) -> Iterable[FundamentalRecord]:
        """Not supported for CSV/Parquet import."""
        return []

    def health(self) -> ProviderHealth:
        """Check if the file is accessible."""
        if self._path.exists():
            return ProviderHealth(name=self.name, status="ok")
        return ProviderHealth(name=self.name, status="down", error_message="File not found")
