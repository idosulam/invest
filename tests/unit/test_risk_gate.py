"""Unit tests for risk gate — PRD Section 5.3."""

from datetime import datetime, timedelta
from decimal import Decimal

import pytest

from packages.risk.gate import RiskGate, RiskGateResult
from packages.strategies.registry.strategy_base import RawSignal
from packages.domain.enums.common import SignalState, QualityGate


def make_signal(state=SignalState.ENTER_LONG, confidence=0.7) -> RawSignal:
    """Create a test signal."""
    return RawSignal(
        state=state,
        confidence=confidence,
        entry_zone_low=Decimal("95"),
        entry_zone_high=Decimal("105"),
        invalidation_rule="Close below 90",
        invalidation_level=Decimal("90"),
        target_method="risk_multiple",
        reason_codes=["test"],
        limitations=[],
    )


class TestRiskGate:
    """Test risk gate evaluation."""

    def test_passes_healthy_signal(self):
        gate = RiskGate()
        signal = make_signal()
        result = gate.evaluate(
            signal=signal,
            instrument_status="ACTIVE",
            last_bar_ts=datetime.utcnow(),
            data_completeness=1.0,
            avg_daily_volume=100000,
        )
        assert result.passed is True
        assert result.quality_gate == QualityGate.PASS

    def test_blocks_inactive_instrument(self):
        gate = RiskGate()
        signal = make_signal()
        result = gate.evaluate(
            signal=signal,
            instrument_status="SUSPENDED",
        )
        assert result.passed is False
        assert result.quality_gate == QualityGate.FAIL

    def test_blocks_stale_data(self):
        gate = RiskGate(max_staleness_hours=24)
        signal = make_signal()
        result = gate.evaluate(
            signal=signal,
            last_bar_ts=datetime.utcnow() - timedelta(hours=48),
        )
        assert result.passed is False

    def test_blocks_low_liquidity(self):
        gate = RiskGate()
        signal = make_signal()
        result = gate.evaluate(
            signal=signal,
            avg_daily_volume=100,  # very low
        )
        assert result.passed is False

    def test_kill_switch_suppresses_all(self):
        gate = RiskGate(kill_switch=True)
        signal = make_signal()
        result = gate.evaluate(signal=signal)
        assert result.passed is False
        assert result.quality_gate == QualityGate.FAIL
        assert "kill switch" in result.blockers[0].lower()

    def test_no_signal_passes_through(self):
        gate = RiskGate()
        signal = make_signal(state=SignalState.NO_SIGNAL, confidence=0)
        result = gate.evaluate(signal=signal)
        assert result.passed is True
        assert result.adjusted_confidence == 0

    def test_confidence_reduced_for_stale_data(self):
        gate = RiskGate(max_staleness_hours=24)
        signal = make_signal(confidence=0.8)
        result = gate.evaluate(
            signal=signal,
            last_bar_ts=datetime.utcnow() - timedelta(hours=30),
        )
        assert result.adjusted_confidence < 0.8

    def test_confidence_reduced_for_conflicting_signals(self):
        gate = RiskGate()
        signal = make_signal(confidence=0.8)
        result = gate.evaluate(
            signal=signal,
            conflicting_signals=2,
        )
        assert result.adjusted_confidence < 0.8

    def test_warn_for_upcoming_event(self):
        gate = RiskGate()
        signal = make_signal()
        result = gate.evaluate(
            signal=signal,
            has_upcoming_event=True,
        )
        # Upcoming event reduces confidence and may block entry
        assert result.adjusted_confidence < signal.confidence
        assert len(result.adjustments) > 0

    def test_blocks_missing_invalidation(self):
        gate = RiskGate()
        signal = make_signal()
        signal.invalidation_level = None
        result = gate.evaluate(signal=signal)
        assert result.passed is False
        assert any("invalidation" in b.lower() for b in result.blockers)
