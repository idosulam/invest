"""Unit tests for confidence methodology — PRD Section 5.4."""

import pytest
from packages.risk.confidence import ConfidenceCalculator, ConfidenceResult


class TestConfidenceCalculator:
    """Test deterministic confidence calculation."""

    def test_basic_calculation(self):
        calc = ConfidenceCalculator()
        result = calc.calculate(
            strategy_validation_score=0.5,
            regime_similarity=0.5,
            feature_completeness=1.0,
            signal_agreement_count=1,
            total_strategies=1,
        )
        assert isinstance(result, ConfidenceResult)
        assert 0 <= result.final_confidence <= 1
        assert len(result.components) == 7

    def test_high_confidence_scenario(self):
        calc = ConfidenceCalculator()
        result = calc.calculate(
            strategy_validation_score=0.9,
            regime_similarity=0.8,
            feature_completeness=1.0,
            signal_agreement_count=3,
            total_strategies=3,
            avg_daily_volume=1000000,
            model_validated=True,
            parameter_sensitivity_score=0.8,
            backtest_sharpe=2.0,
            backtest_win_rate=0.65,
        )
        assert result.final_confidence > 0.7
        assert len(result.caps_applied) == 0

    def test_low_confidence_scenario(self):
        calc = ConfidenceCalculator()
        result = calc.calculate(
            strategy_validation_score=0.2,
            regime_similarity=0.1,
            feature_completeness=0.5,
            signal_agreement_count=0,
            total_strategies=3,
            avg_daily_volume=100,
            data_staleness_hours=72,
            model_validated=False,
            parameter_sensitivity_score=0.2,
        )
        assert result.final_confidence < 0.4
        assert len(result.caps_applied) > 0

    def test_staleness_cap(self):
        calc = ConfidenceCalculator()
        result = calc.calculate(
            data_staleness_hours=100,
        )
        assert any("stale" in cap.lower() for cap in result.caps_applied)

    def test_regime_cap(self):
        calc = ConfidenceCalculator()
        result = calc.calculate(
            regime_similarity=0.1,
        )
        assert any("regime" in cap.lower() for cap in result.caps_applied)

    def test_custom_weights(self):
        weights = {
            "strategy_validation": 0.5,
            "regime_similarity": 0.1,
            "feature_completeness": 0.1,
            "signal_agreement": 0.1,
            "liquidity": 0.1,
            "model_calibration": 0.05,
            "parameter_sensitivity": 0.05,
        }
        calc = ConfidenceCalculator(weights=weights)
        result = calc.calculate(
            strategy_validation_score=0.9,
            regime_similarity=0.1,
        )
        # High validation weight should dominate
        assert result.final_confidence > 0.3

    def test_components_stored_separately(self):
        calc = ConfidenceCalculator()
        result = calc.calculate()
        component_names = [c.name for c in result.components]
        assert "strategy_validation" in component_names
        assert "regime_similarity" in component_names
        assert "feature_completeness" in component_names
        assert "signal_agreement" in component_names
        assert "liquidity" in component_names
        assert "model_calibration" in component_names
        assert "parameter_sensitivity" in component_names
