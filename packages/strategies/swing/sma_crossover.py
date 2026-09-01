"""SMA Crossover strategy — PRD Section 5.2 (Swing).

Generates signals when short SMA crosses long SMA.
Entry on golden cross, exit on death cross.
"""

from decimal import Decimal
from packages.strategies.registry.strategy_base import (
    Strategy, StrategyCard, FeatureSpec, MarketContext, RawSignal, RiskPlan,
    StrategyRegistry,
)
from packages.domain.enums.common import Horizon, SignalState


@StrategyRegistry.register
class SMACrossover(Strategy):
    """SMA 20/50 crossover for swing trading."""

    @property
    def metadata(self) -> StrategyCard:
        return StrategyCard(
            name="SMA Crossover 20/50",
            version="1.0.0",
            horizon=Horizon.SWING,
            description="Buy when SMA(20) crosses above SMA(50), sell when it crosses below. Trend-following strategy.",
            tags=["trend", "moving-average", "swing"],
            required_lookback=60,
        )

    def required_features(self) -> list[FeatureSpec]:
        return [
            FeatureSpec(name="sma_20", params={"period": 20}),
            FeatureSpec(name="sma_50", params={"period": 50}),
            FeatureSpec(name="atr_14", params={"period": 14}),
        ]

    def generate(self, context: MarketContext) -> RawSignal:
        close = context.bars["close"]
        sma_20 = context.indicators.get("sma_20")
        sma_50 = context.indicators.get("sma_50")
        atr_14 = context.indicators.get("atr_14")

        if sma_20 is None or sma_50 is None or len(close) < 55:
            return RawSignal(state=SignalState.NO_SIGNAL, confidence=0, limitations=["Insufficient data"])

        curr_sma20 = float(sma_20.iloc[-1])
        curr_sma50 = float(sma_50.iloc[-1])
        prev_sma20 = float(sma_20.iloc[-2])
        prev_sma50 = float(sma_50.iloc[-2])
        curr_price = float(close.iloc[-1])
        curr_atr = float(atr_14.iloc[-1]) if atr_14 is not None and not atr_14.isna().iloc[-1] else curr_price * 0.02

        # Golden cross: SMA20 crosses above SMA50
        golden_cross = prev_sma20 <= prev_sma50 and curr_sma20 > curr_sma50
        # Death cross: SMA20 crosses below SMA50
        death_cross = prev_sma20 >= prev_sma50 and curr_sma20 < curr_sma50
        # Already trending up
        uptrend = curr_sma20 > curr_sma50
        # Already trending down
        downtrend = curr_sma20 < curr_sma50

        reason_codes = []
        limitations = []

        if golden_cross:
            state = SignalState.ENTER_LONG
            confidence = 0.7
            reason_codes.append("golden_cross")
            reason_codes.append("sma20_above_sma50")
        elif uptrend and curr_price > curr_sma20:
            state = SignalState.HOLD
            confidence = 0.5
            reason_codes.append("uptrend_continues")
        elif death_cross:
            state = SignalState.EXIT
            confidence = 0.7
            reason_codes.append("death_cross")
        elif downtrend:
            state = SignalState.WATCH
            confidence = 0.3
            reason_codes.append("downtrend")
            limitations.append("Waiting for reversal signal")
        else:
            state = SignalState.NO_SIGNAL
            confidence = 0.0

        # Confidence adjustments
        if state != SignalState.NO_SIGNAL:
            # Volume confirmation
            vol = context.bars["volume"]
            if len(vol) >= 20:
                avg_vol = float(vol.tail(20).mean())
                curr_vol = float(vol.iloc[-1])
                if curr_vol > avg_vol * 1.5:
                    confidence = min(confidence + 0.1, 1.0)
                    reason_codes.append("volume_confirmation")

            # Price distance from SMA (mean reversion risk)
            distance_pct = abs(curr_price - curr_sma20) / curr_sma20
            if distance_pct > 0.05:
                confidence = max(confidence - 0.1, 0.0)
                limitations.append("Price extended from SMA — pullback risk")

        entry_low = Decimal(str(round(curr_price - curr_atr, 2)))
        entry_high = Decimal(str(round(curr_price + curr_atr * 0.5, 2)))

        return RawSignal(
            state=state,
            confidence=round(confidence, 4),
            entry_zone_low=entry_low if state == SignalState.ENTER_LONG else None,
            entry_zone_high=entry_high if state == SignalState.ENTER_LONG else None,
            invalidation_rule="Close below SMA(50)" if state == SignalState.ENTER_LONG else "",
            invalidation_level=Decimal(str(round(curr_sma50, 2))) if state == SignalState.ENTER_LONG else None,
            target_method="risk_multiple",
            reason_codes=reason_codes,
            limitations=limitations,
        )

    def risk_plan(self, signal: RawSignal, portfolio_value: Decimal = Decimal("100000")) -> RiskPlan:
        if signal.state == SignalState.ENTER_LONG and signal.invalidation_level:
            entry_mid = (signal.entry_zone_low + signal.entry_zone_high) / 2 if signal.entry_zone_low and signal.entry_zone_high else entry_mid
            stop = signal.invalidation_level
            risk_per_share = entry_mid - stop if entry_mid > stop else entry_mid * Decimal("0.02")
            return RiskPlan(
                max_loss_pct=Decimal("2.0"),
                suggested_size_pct=Decimal("5.0"),
                stop_loss=stop,
                take_profit=entry_mid + (risk_per_share * Decimal("3")) if risk_per_share > 0 else None,
            )
        return RiskPlan()
