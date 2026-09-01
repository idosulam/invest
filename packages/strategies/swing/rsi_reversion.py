"""RSI Mean Reversion strategy — PRD Section 5.2 (Swing).

Buys oversold bounces, sells overbought reversions.
"""

from decimal import Decimal
from packages.strategies.registry.strategy_base import (
    Strategy, StrategyCard, FeatureSpec, MarketContext, RawSignal, RiskPlan,
    StrategyRegistry,
)
from packages.domain.enums.common import Horizon, SignalState


@StrategyRegistry.register
class RSIMeanReversion(Strategy):
    """RSI(14) mean reversion — buy oversold, sell overbought."""

    @property
    def metadata(self) -> StrategyCard:
        return StrategyCard(
            name="RSI Mean Reversion",
            version="1.0.0",
            horizon=Horizon.SWING,
            description="Buy when RSI(14) drops below 30 and starts recovering. Sell when RSI exceeds 70.",
            tags=["momentum", "mean-reversion", "swing"],
            required_lookback=30,
        )

    def required_features(self) -> list[FeatureSpec]:
        return [
            FeatureSpec(name="rsi_14", params={"period": 14}),
            FeatureSpec(name="atr_14", params={"period": 14}),
            FeatureSpec(name="sma_50", params={"period": 50}),
        ]

    def generate(self, context: MarketContext) -> RawSignal:
        close = context.bars["close"]
        rsi = context.indicators.get("rsi_14")
        atr_14 = context.indicators.get("atr_14")
        sma_50 = context.indicators.get("sma_50")

        if rsi is None or len(close) < 20:
            return RawSignal(state=SignalState.NO_SIGNAL, confidence=0, limitations=["Insufficient data"])

        curr_rsi = float(rsi.iloc[-1])
        prev_rsi = float(rsi.iloc[-2])
        curr_price = float(close.iloc[-1])
        curr_atr = float(atr_14.iloc[-1]) if atr_14 is not None and not atr_14.isna().iloc[-1] else curr_price * 0.02
        curr_sma50 = float(sma_50.iloc[-1]) if sma_50 is not None and not sma_50.isna().iloc[-1] else None

        reason_codes = []
        limitations = []

        # Oversold bounce: RSI was below 30, now crossing back above
        if prev_rsi < 30 and curr_rsi >= 30:
            state = SignalState.ENTER_LONG
            confidence = 0.65
            reason_codes.append("rsi_oversold_bounce")
            reason_codes.append("rsi_crossing_above_30")
        # Deeply oversold
        elif curr_rsi < 25:
            state = SignalState.WATCH
            confidence = 0.5
            reason_codes.append("rsi_deeply_oversold")
            limitations.append("RSI still declining — wait for bounce confirmation")
        # Overbought reversal
        elif curr_rsi > 70 and prev_rsi > curr_rsi:
            state = SignalState.EXIT
            confidence = 0.6
            reason_codes.append("rsi_overbought_reversal")
        # Overbought
        elif curr_rsi > 70:
            state = SignalState.REDUCE
            confidence = 0.5
            reason_codes.append("rsi_overbought")
        # Neutral
        elif 40 <= curr_rsi <= 60:
            state = SignalState.HOLD
            confidence = 0.3
            reason_codes.append("rsi_neutral")
        else:
            state = SignalState.NO_SIGNAL
            confidence = 0.0

        # Trend filter: penalize signals against the trend
        if state == SignalState.ENTER_LONG and curr_sma50 is not None:
            if curr_price < curr_sma50 * 0.95:
                confidence = max(confidence - 0.15, 0.0)
                limitations.append("Below SMA(50) — counter-trend trade")
            elif curr_price > curr_sma50:
                confidence = min(confidence + 0.05, 1.0)
                reason_codes.append("trend_aligned")

        entry_low = Decimal(str(round(curr_price - curr_atr * 0.5, 2)))
        entry_high = Decimal(str(round(curr_price + curr_atr * 0.3, 2)))

        return RawSignal(
            state=state,
            confidence=round(confidence, 4),
            entry_zone_low=entry_low if state == SignalState.ENTER_LONG else None,
            entry_zone_high=entry_high if state == SignalState.ENTER_LONG else None,
            invalidation_rule="RSI drops back below 25" if state == SignalState.ENTER_LONG else "",
            invalidation_level=Decimal(str(round(curr_price - curr_atr * 2, 2))) if state == SignalState.ENTER_LONG else None,
            target_method="volatility_band",
            reason_codes=reason_codes,
            limitations=limitations,
        )

    def risk_plan(self, signal: RawSignal, portfolio_value: Decimal = Decimal("100000")) -> RiskPlan:
        return RiskPlan(
            max_loss_pct=Decimal("1.5"),
            suggested_size_pct=Decimal("4.0"),
            stop_loss=signal.invalidation_level,
        )
