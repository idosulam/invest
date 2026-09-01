"""Confidence methodology — PRD Section 5.4.

Deterministic confidence calculation from component scores.
Each component is scored independently, then combined with weights.
Caps are applied for stale data, unseen regimes, or unstable parameters.

The LLM may explain these components but cannot modify them.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional


@dataclass
class ConfidenceComponent:
    """Individual confidence component with score and rationale."""
    name: str
    score: float  # 0.0 - 1.0
    weight: float  # contribution weight
    rationale: str = ""


@dataclass
class ConfidenceResult:
    """Full confidence breakdown."""
    final_confidence: float
    components: list[ConfidenceComponent]
    caps_applied: list[str] = field(default_factory=list)
    raw_score: float = 0.0


class ConfidenceCalculator:
    """Deterministic confidence scorer — PRD Section 5.4.

    Calculates confidence from:
    1. Strategy validation score (how well has this strategy performed?)
    2. Regime similarity (is current market like backtest periods?)
    3. Feature completeness (are all required indicators available?)
    4. Signal agreement (do multiple strategies agree?)
    5. Liquidity (is the instrument liquid enough?)
    6. Model calibration (has the model been validated?)
    7. Parameter sensitivity (how stable is the signal to small changes?)
    """

    # Default weights
    DEFAULT_WEIGHTS = {
        "strategy_validation": 0.20,
        "regime_similarity": 0.15,
        "feature_completeness": 0.15,
        "signal_agreement": 0.20,
        "liquidity": 0.10,
        "model_calibration": 0.10,
        "parameter_sensitivity": 0.10,
    }

    def __init__(self, weights: Optional[dict[str, float]] = None):
        self.weights = weights or self.DEFAULT_WEIGHTS
        # Normalize weights to sum to 1.0
        total = sum(self.weights.values())
        if total > 0:
            self.weights = {k: v / total for k, v in self.weights.items()}

    def calculate(
        self,
        strategy_validation_score: float = 0.5,
        regime_similarity: float = 0.5,
        feature_completeness: float = 1.0,
        signal_agreement_count: int = 1,
        total_strategies: int = 1,
        avg_daily_volume: float = 0.0,
        data_staleness_hours: float = 0.0,
        model_validated: bool = False,
        parameter_sensitivity_score: float = 0.5,
        backtest_sharpe: Optional[float] = None,
        backtest_win_rate: Optional[float] = None,
    ) -> ConfidenceResult:
        """Calculate confidence from component scores.

        Args:
            strategy_validation_score: 0-1 score from backtest validation.
            regime_similarity: 0-1 similarity to validated market regimes.
            feature_completeness: 0-1 fraction of required features available.
            signal_agreement_count: Number of strategies producing same signal direction.
            total_strategies: Total strategies evaluated.
            avg_daily_volume: Average daily volume for liquidity scoring.
            data_staleness_hours: Hours since last data update.
            model_validated: Whether ML model has been validated.
            parameter_sensitivity_score: 0-1 stability score (1 = stable).
            backtest_sharpe: Sharpe ratio from backtest (optional).
            backtest_win_rate: Win rate from backtest (optional).

        Returns:
            ConfidenceResult with final score and breakdown.
        """
        components = []
        caps = []

        # 1. Strategy validation score
        validation_score = strategy_validation_score
        if backtest_sharpe is not None:
            # Boost validation if backtest metrics are strong
            if backtest_sharpe > 1.5:
                validation_score = min(validation_score + 0.15, 1.0)
            elif backtest_sharpe > 1.0:
                validation_score = min(validation_score + 0.1, 1.0)
            elif backtest_sharpe < 0:
                validation_score = max(validation_score - 0.2, 0.0)
        if backtest_win_rate is not None:
            if backtest_win_rate > 0.6:
                validation_score = min(validation_score + 0.05, 1.0)
            elif backtest_win_rate < 0.4:
                validation_score = max(validation_score - 0.1, 0.0)

        components.append(ConfidenceComponent(
            name="strategy_validation",
            score=round(validation_score, 4),
            weight=self.weights["strategy_validation"],
            rationale=f"Backtest validation score: {validation_score:.2f}",
        ))

        # 2. Regime similarity
        components.append(ConfidenceComponent(
            name="regime_similarity",
            score=round(regime_similarity, 4),
            weight=self.weights["regime_similarity"],
            rationale=f"Current regime similarity to validated periods: {regime_similarity:.2f}",
        ))

        # 3. Feature completeness
        components.append(ConfidenceComponent(
            name="feature_completeness",
            score=round(feature_completeness, 4),
            weight=self.weights["feature_completeness"],
            rationale=f"Feature completeness: {feature_completeness:.0%}",
        ))
        if feature_completeness < 0.8:
            caps.append(f"Feature completeness low ({feature_completeness:.0%}) — confidence capped")

        # 4. Signal agreement
        if total_strategies > 0:
            agreement_ratio = signal_agreement_count / total_strategies
        else:
            agreement_ratio = 0.0
        agreement_score = min(agreement_ratio * 1.5, 1.0)  # Bonus for consensus

        components.append(ConfidenceComponent(
            name="signal_agreement",
            score=round(agreement_score, 4),
            weight=self.weights["signal_agreement"],
            rationale=f"{signal_agreement_count}/{total_strategies} strategies agree",
        ))

        # 5. Liquidity
        if avg_daily_volume >= 1_000_000:
            liquidity_score = 1.0
        elif avg_daily_volume >= 100_000:
            liquidity_score = 0.8
        elif avg_daily_volume >= 10_000:
            liquidity_score = 0.5
        elif avg_daily_volume > 0:
            liquidity_score = 0.2
            caps.append("Low liquidity — confidence capped at 0.6")
        else:
            liquidity_score = 0.0
            caps.append("No volume data — confidence capped at 0.4")

        components.append(ConfidenceComponent(
            name="liquidity",
            score=round(liquidity_score, 4),
            weight=self.weights["liquidity"],
            rationale=f"Avg daily volume: {avg_daily_volume:,.0f}",
        ))

        # 6. Model calibration
        calibration_score = 0.7 if model_validated else 0.3
        components.append(ConfidenceComponent(
            name="model_calibration",
            score=round(calibration_score, 4),
            weight=self.weights["model_calibration"],
            rationale="Model validated" if model_validated else "Model not validated — default score",
        ))

        # 7. Parameter sensitivity
        components.append(ConfidenceComponent(
            name="parameter_sensitivity",
            score=round(parameter_sensitivity_score, 4),
            weight=self.weights["parameter_sensitivity"],
            rationale=f"Parameter sensitivity: {parameter_sensitivity_score:.2f} (1.0 = stable)",
        ))
        if parameter_sensitivity_score < 0.3:
            caps.append("High parameter sensitivity — signal unstable")

        # Calculate weighted score
        raw_score = sum(c.score * c.weight for c in components)

        # Apply staleness cap
        if data_staleness_hours > 48:
            staleness_cap = max(0.3, 1.0 - (data_staleness_hours - 48) / 168)
            caps.append(f"Data stale ({data_staleness_hours:.0f}h) — capped at {staleness_cap:.2f}")
        elif data_staleness_hours > 24:
            staleness_cap = 0.85
            caps.append(f"Data {data_staleness_hours:.0f}h old — slight cap")
        else:
            staleness_cap = 1.0

        # Apply regime cap
        if regime_similarity < 0.2:
            regime_cap = 0.5
            caps.append("Unseen regime — confidence capped at 0.5")
        elif regime_similarity < 0.4:
            regime_cap = 0.7
            caps.append("Low regime similarity — confidence capped at 0.7")
        else:
            regime_cap = 1.0

        # Apply all caps
        final = raw_score * staleness_cap * regime_cap
        final = round(min(max(final, 0.0), 1.0), 4)

        return ConfidenceResult(
            final_confidence=final,
            components=components,
            caps_applied=caps,
            raw_score=round(raw_score, 4),
        )
