"""Quality/Value Composite strategy — PRD Section 5.2 (Long-term).

Combines trend filter with fundamental valuation signals.
"""

from decimal import Decimal
from packages.strategies.registry.strategy_base import (
    Strategy, StrategyCard, FeatureSpec, MarketContext, RawSignal, RiskPlan,
    StrategyRegistry,
)
from packages.domain.enums.common import Horizon, SignalState


@StrategyRegistry.register
class QualityValueComposite(Strategy):
    """Long-term quality/value: 200-day trend + fundamental screening."""

    @property
    def metadata(self) -> StrategyCard:
        return StrategyCard(
            name="Quality/Value Composite",
            version="1.0.0",
            horizon=Horizon.LONG_TERM,
            description="Buy quality companies in uptrends at reasonable valuations. Uses SMA(200) trend filter + P/E and profitability screens.",
            tags=["fundamental", "value", "long-term", "quality"],
            required_lookback=200,
        )

    def required_features(self) -> list[FeatureSpec]:
        return [
            FeatureSpec(name="sma_200", params={"period": 200}),
            FeatureSpec(name="sma_50", params={"period": 50}),
            FeatureSpec(name="rsi_14", params={"period": 14}),
            FeatureSpec(name="atr_14", params={"period": 14}),
        ]

    def generate(self, context: MarketContext) -> RawSignal:
        close = context.bars["close"]
        sma_200 = context.indicators.get("sma_200")
        sma_50 = context.indicators.get("sma_50")
        rsi = context.indicators.get("rsi_14")
        atr_14 = context.indicators.get("atr_14")

        if sma_200 is None or len(close) < 200:
            return RawSignal(state=SignalState.NO_SIGNAL, confidence=0, limitations=["Need 200+ bars"])

        curr_price = float(close.iloc[-1])
        curr_sma200 = float(sma_200.iloc[-1])
        curr_sma50 = float(sma_50.iloc[-1]) if sma_50 is not None and not sma_50.isna().iloc[-1] else None
        curr_rsi = float(rsi.iloc[-1]) if rsi is not None and not rsi.isna().iloc[-1] else 50
        curr_atr = float(atr_14.iloc[-1]) if atr_14 is not None and not atr_14.isna().iloc[-1] else curr_price * 0.02

        reason_codes = []
        limitations = []

        # Fundamental checks
        pe = context.fundamentals.get("pe_ratio_ttm")
        roe = context.fundamentals.get("roe")
        profit_margin = context.fundamentals.get("profit_margin")

        # Trend filter: must be above SMA(200)
        above_sma200 = curr_price > curr_sma200

        # Valuation score
        valuation_ok = True
        if pe is not None:
            if pe < 0:
                valuation_ok = False
                limitations.append("Negative earnings")
            elif pe > 35:
                valuation_ok = False
                limitations.append("P/E too high (>35)")
            elif pe < 25:
                reason_codes.append("reasonable_pe")
                valuation_ok = True

        # Quality score
        quality_score = 0
        if roe is not None and roe > 0.15:
            quality_score += 1
            reason_codes.append("strong_roe")
        if profit_margin is not None and profit_margin > 0.1:
            quality_score += 1
            reason_codes.append("healthy_margins")

        # Generate signal
        if above_sma200 and valuation_ok and quality_score >= 1:
            # Check for pullback entry (price near SMA50)
            if curr_sma50 is not None and curr_price < curr_sma50 * 1.05:
                state = SignalState.ENTER_LONG
                confidence = 0.7
                reason_codes.append("pullback_to_sma50")
                reason_codes.append("above_sma200")
            elif curr_rsi < 45:
                state = SignalState.ENTER_LONG
                confidence = 0.6
                reason_codes.append("rsi_pullback")
                reason_codes.append("above_sma200")
            else:
                state = SignalState.HOLD
                confidence = 0.4
                reason_codes.append("uptrend_no_entry")
        elif above_sma200:
            state = SignalState.WATCH
            confidence = 0.3
            reason_codes.append("above_sma200")
            if not valuation_ok:
                limitations.append("Valuation criteria not met")
            if quality_score < 1:
                limitations.append("Quality criteria not met")
        else:
            state = SignalState.NO_SIGNAL
            confidence = 0.0
            reason_codes.append("below_sma200")

        entry_low = Decimal(str(round(curr_price - curr_atr, 2)))
        entry_high = Decimal(str(round(curr_price + curr_atr * 0.5, 2)))

        return RawSignal(
            state=state,
            confidence=round(confidence, 4),
            entry_zone_low=entry_low if state == SignalState.ENTER_LONG else None,
            entry_zone_high=entry_high if state == SignalState.ENTER_LONG else None,
            invalidation_rule="Close below SMA(200)" if state == SignalState.ENTER_LONG else "",
            invalidation_level=Decimal(str(round(curr_sma200, 2))) if state == SignalState.ENTER_LONG else None,
            target_method="fundamental_value",
            reason_codes=reason_codes,
            limitations=limitations,
        )

    def risk_plan(self, signal: RawSignal, portfolio_value: Decimal = Decimal("100000")) -> RiskPlan:
        return RiskPlan(
            max_loss_pct=Decimal("3.0"),
            suggested_size_pct=Decimal("8.0"),
            stop_loss=signal.invalidation_level,
        )
