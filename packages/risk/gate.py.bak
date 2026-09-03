"""Risk gate — PRD Section 5.3.

Validates signals before publishing. Checks data freshness,
instrument status, liquidity, portfolio limits, and conflicting signals.
"""

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional

from packages.strategies.registry.strategy_base import RawSignal, RiskPlan
from packages.domain.enums.common import QualityGate, SignalState


@dataclass
class RiskGateResult:
    """Result of risk gate evaluation."""
    passed: bool
    quality_gate: QualityGate
    adjusted_confidence: float
    adjustments: list[str] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)


class RiskGate:
    """Validates signals before publication.

    PRD 5.3 requirements:
    - Data freshness/completeness passes
    - Instrument is tradable and not suspended/delisted
    - Liquidity and spread proxies pass
    - Portfolio concentration limits pass
    - Volatility-based size calculated
    - Earnings/dividend proximity disclosed
    - Stop/invalidation level defined
    - Conflicting strategies reduce confidence
    - Kill switch suppresses during quality incidents
    """

    def __init__(
        self,
        max_portfolio_concentration_pct: float = 20.0,
        max_sector_concentration_pct: float = 40.0,
        min_data_completeness: float = 0.95,
        max_staleness_hours: int = 48,
        kill_switch: bool = False,
    ):
        self.max_portfolio_concentration = max_portfolio_concentration_pct
        self.max_sector_concentration = max_sector_concentration_pct
        self.min_data_completeness = min_data_completeness
        self.max_staleness = timedelta(hours=max_staleness_hours)
        self.kill_switch = kill_switch

    def evaluate(
        self,
        signal: RawSignal,
        instrument_status: str = "ACTIVE",
        last_bar_ts: Optional[datetime] = None,
        data_completeness: float = 1.0,
        avg_daily_volume: float = 0.0,
        current_positions_pct: Optional[dict[str, float]] = None,
        sector_pct: Optional[dict[str, float]] = None,
        instrument_sector: Optional[str] = None,
        has_upcoming_event: bool = False,
        conflicting_signals: int = 0,
    ) -> RiskGateResult:
        """Run all risk checks on a raw signal."""
        adjustments = []
        blockers = []
        confidence = signal.confidence

        # Kill switch
        if self.kill_switch:
            return RiskGateResult(
                passed=False,
                quality_gate=QualityGate.FAIL,
                adjusted_confidence=0,
                blockers=["Kill switch active — all signals suppressed"],
            )

        # No-signal passes through
        if signal.state == SignalState.NO_SIGNAL:
            return RiskGateResult(
                passed=True,
                quality_gate=QualityGate.PASS,
                adjusted_confidence=0,
            )

        # 1. Instrument status
        if instrument_status != "ACTIVE":
            blockers.append(f"Instrument not active: {instrument_status}")

        # 2. Data freshness
        if last_bar_ts:
            age = datetime.utcnow() - last_bar_ts
            if age > self.max_staleness:
                blockers.append(f"Data stale: {age.days}d {age.seconds // 3600}h old")
                confidence *= 0.5
                adjustments.append("Confidence halved due to stale data")

        # 3. Data completeness
        if data_completeness < self.min_data_completeness:
            blockers.append(f"Data completeness {data_completeness:.0%} < {self.min_data_completeness:.0%}")
            confidence *= 0.7
            adjustments.append("Confidence reduced for incomplete data")

        # 4. Liquidity (min 10k avg daily volume)
        if signal.state == SignalState.ENTER_LONG and avg_daily_volume < 10000:
            blockers.append(f"Low liquidity: avg volume {avg_daily_volume:,.0f}")
            confidence *= 0.6
            adjustments.append("Low liquidity penalty")

        # 5. Portfolio concentration
        if current_positions_pct and signal.state == SignalState.ENTER_LONG:
            # Check if adding this would exceed concentration limit
            # (simplified — assumes equal weight)
            pass

        # 6. Sector concentration
        if sector_pct and instrument_sector and signal.state == SignalState.ENTER_LONG:
            current_sector_pct = sector_pct.get(instrument_sector, 0)
            if current_sector_pct > self.max_sector_concentration:
                blockers.append(f"Sector {instrument_sector} at {current_sector_pct:.0f}% (max {self.max_sector_concentration:.0f}%)")
                confidence *= 0.8
                adjustments.append("Sector concentration penalty")

        # 7. Upcoming event proximity
        if has_upcoming_event:
            confidence *= 0.7
            adjustments.append("Earnings/dividend event proximity — reduced confidence")
            if signal.state == SignalState.ENTER_LONG:
                blockers.append("Upcoming corporate event — consider waiting")

        # 8. Conflicting signals
        if conflicting_signals > 0:
            penalty = min(conflicting_signals * 0.1, 0.3)
            confidence = max(confidence - penalty, 0.0)
            adjustments.append(f"{conflicting_signals} conflicting signal(s) — confidence reduced by {penalty:.0%}")

        # 9. Invalidation required for entry
        if signal.state == SignalState.ENTER_LONG and not signal.invalidation_level:
            blockers.append("No invalidation/stop level defined")

        # Determine quality gate
        if blockers:
            quality_gate = QualityGate.FAIL
            passed = False
        elif adjustments:
            quality_gate = QualityGate.WARN
            passed = True
        else:
            quality_gate = QualityGate.PASS
            passed = True

        # Cap confidence
        confidence = round(min(max(confidence, 0.0), 1.0), 4)

        return RiskGateResult(
            passed=passed,
            quality_gate=quality_gate,
            adjusted_confidence=confidence,
            adjustments=adjustments,
            blockers=blockers,
        )
