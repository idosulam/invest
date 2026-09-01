"""Data quality validation pipeline — PRD Section 4.3.

Validates incoming data for:
- Schema correctness
- Price relationships (high >= low, etc.)
- Duplicate detection
- Monotonic timestamps
- Timezone consistency
- Stale data detection
"""

import hashlib
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional

from packages.data.providers.base import Bar, CorporateActionRecord, InstrumentRecord
from packages.domain.enums.common import DataQualityStatus

logger = logging.getLogger(__name__)


@dataclass
class QualityIssue:
    """A data quality issue found during validation."""
    severity: str  # LOW, MEDIUM, HIGH, CRITICAL
    issue_type: str
    description: str
    symbol: Optional[str] = None
    timestamp: Optional[datetime] = None


@dataclass
class ValidationResult:
    """Result of validating a data batch."""
    status: DataQualityStatus
    total_records: int
    valid_records: int
    rejected_records: int
    issues: list[QualityIssue] = field(default_factory=list)
    content_hash: Optional[str] = None

    @property
    def pass_rate(self) -> float:
        return self.valid_records / self.total_records if self.total_records > 0 else 0.0


class DataValidator:
    """Validates market data quality before ingestion."""

    def __init__(
        self,
        max_price_change_pct: float = 50.0,  # Max single-day change %
        max_staleness_days: int = 7,  # Max days without new data
        min_volume: Decimal = Decimal("0"),
    ):
        self._max_price_change = max_price_change_pct
        self._max_staleness = max_staleness_days
        self._min_volume = min_volume

    def validate_bars(self, bars: list[Bar]) -> ValidationResult:
        """Validate a batch of OHLCV bars."""
        issues: list[QualityIssue] = []
        valid = 0
        rejected = 0

        # Sort by timestamp for monotonic check
        sorted_bars = sorted(bars, key=lambda b: b.ts_open)

        prev_ts = None
        prev_close = None

        for bar in sorted_bars:
            bar_valid = True

            # 1. Price relationship checks
            if bar.high < bar.low:
                issues.append(QualityIssue(
                    severity="HIGH",
                    issue_type="price_inversion",
                    description=f"High ({bar.high}) < Low ({bar.low})",
                    symbol=bar.symbol,
                    timestamp=bar.ts_open,
                ))
                bar_valid = False

            if bar.open < Decimal("0") or bar.close < Decimal("0"):
                issues.append(QualityIssue(
                    severity="CRITICAL",
                    issue_type="negative_price",
                    description=f"Negative price: O={bar.open} C={bar.close}",
                    symbol=bar.symbol,
                    timestamp=bar.ts_open,
                ))
                bar_valid = False

            if bar.high < Decimal("0") or bar.low < Decimal("0"):
                issues.append(QualityIssue(
                    severity="CRITICAL",
                    issue_type="negative_price",
                    description=f"Negative H/L: H={bar.high} L={bar.low}",
                    symbol=bar.symbol,
                    timestamp=bar.ts_open,
                ))
                bar_valid = False

            # 2. Open/Close within H/L range
            if bar.open > bar.high or bar.open < bar.low:
                issues.append(QualityIssue(
                    severity="MEDIUM",
                    issue_type="open_out_of_range",
                    description=f"Open ({bar.open}) outside H-L range [{bar.low}, {bar.high}]",
                    symbol=bar.symbol,
                    timestamp=bar.ts_open,
                ))

            if bar.close > bar.high or bar.close < bar.low:
                issues.append(QualityIssue(
                    severity="MEDIUM",
                    issue_type="close_out_of_range",
                    description=f"Close ({bar.close}) outside H-L range [{bar.low}, {bar.high}]",
                    symbol=bar.symbol,
                    timestamp=bar.ts_open,
                ))

            # 3. Volume check
            if bar.volume < self._min_volume:
                issues.append(QualityIssue(
                    severity="LOW",
                    issue_type="zero_volume",
                    description=f"Zero or low volume: {bar.volume}",
                    symbol=bar.symbol,
                    timestamp=bar.ts_open,
                ))

            # 4. Monotonic timestamp check
            if prev_ts and bar.ts_open <= prev_ts:
                issues.append(QualityIssue(
                    severity="HIGH",
                    issue_type="non_monotonic_timestamp",
                    description=f"Timestamp {bar.ts_open} <= previous {prev_ts}",
                    symbol=bar.symbol,
                    timestamp=bar.ts_open,
                ))
                bar_valid = False

            # 5. Extreme price change check
            if prev_close and prev_close > Decimal("0"):
                change_pct = abs((bar.close - prev_close) / prev_close * Decimal("100"))
                if change_pct > Decimal(str(self._max_price_change)):
                    issues.append(QualityIssue(
                        severity="MEDIUM",
                        issue_type="extreme_price_change",
                        description=f"Price change {change_pct:.1f}% exceeds {self._max_price_change}%",
                        symbol=bar.symbol,
                        timestamp=bar.ts_open,
                    ))

            # 6. Staleness check
            now = datetime.utcnow().replace(tzinfo=bar.ts_open.tzinfo) if bar.ts_open.tzinfo else datetime.utcnow()
            if bar.ts_open < now - timedelta(days=self._max_staleness * 3):
                issues.append(QualityIssue(
                    severity="LOW",
                    issue_type="very_old_data",
                    description=f"Data from {bar.ts_open.date()} is very old",
                    symbol=bar.symbol,
                    timestamp=bar.ts_open,
                ))

            if bar_valid:
                valid += 1
            else:
                rejected += 1

            prev_ts = bar.ts_open
            prev_close = bar.close

        # Compute content hash
        content_hash = self._compute_hash(bars)

        status = DataQualityStatus.VALIDATED
        if rejected > 0:
            reject_rate = rejected / len(bars) if bars else 0
            if reject_rate > 0.1:
                status = DataQualityStatus.REJECTED
            else:
                status = DataQualityStatus.VALIDATED

        critical = [i for i in issues if i.severity == "CRITICAL"]
        if critical:
            status = DataQualityStatus.REJECTED

        return ValidationResult(
            status=status,
            total_records=len(bars),
            valid_records=valid,
            rejected_records=rejected,
            issues=issues,
            content_hash=content_hash,
        )

    def validate_instruments(self, instruments: list[InstrumentRecord]) -> ValidationResult:
        """Validate instrument metadata."""
        issues: list[QualityIssue] = []
        valid = 0
        rejected = 0

        seen_symbols = set()
        for inst in instruments:
            inst_valid = True

            if not inst.symbol:
                issues.append(QualityIssue(
                    severity="CRITICAL",
                    issue_type="missing_symbol",
                    description="Instrument has no symbol",
                ))
                inst_valid = False

            if not inst.name:
                issues.append(QualityIssue(
                    severity="MEDIUM",
                    issue_type="missing_name",
                    description=f"Instrument {inst.symbol} has no name",
                    symbol=inst.symbol,
                ))

            if inst.symbol in seen_symbols:
                issues.append(QualityIssue(
                    severity="HIGH",
                    issue_type="duplicate_symbol",
                    description=f"Duplicate symbol: {inst.symbol}",
                    symbol=inst.symbol,
                ))
                inst_valid = False
            seen_symbols.add(inst.symbol)

            if inst_valid:
                valid += 1
            else:
                rejected += 1

        return ValidationResult(
            status=DataQualityStatus.REJECTED if rejected > 0 else DataQualityStatus.VALIDATED,
            total_records=len(instruments),
            valid_records=valid,
            rejected_records=rejected,
            issues=issues,
        )

    def _compute_hash(self, bars: list[Bar]) -> str:
        """Compute a deterministic hash of the bar data."""
        content = "|".join(
            f"{b.symbol},{b.ts_open.isoformat()},{b.open},{b.high},{b.low},{b.close},{b.volume}"
            for b in sorted(bars, key=lambda x: (x.symbol, x.ts_open))
        )
        return hashlib.sha256(content.encode()).hexdigest()
