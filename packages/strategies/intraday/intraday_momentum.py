"""Intraday Momentum strategy — PRD Section 5.2 (Intraday).

Trades strong intraday momentum moves with volume surge confirmation.
Uses rate of change, RSI, and ADX for trend strength validation.
Paper trading only for MVP.
"""

from decimal import Decimal
from packages.strategies.registry.strategy_base import (
    Strategy, StrategyCard, FeatureSpec, MarketContext, RawSignal, RiskPlan,
    StrategyRegistry,
)
from packages.domain.enums.common import Horizon, SignalState


@StrategyRegistry.register
class IntradayMomentum(Strategy):
    """Intraday Momentum — ride strong directional moves with volume."""

    @property
    def metadata(self) -> StrategyCard:
        return StrategyCard(
            name="Intraday Momentum",
            version="1.0.0",
            horizon=Horizon.INTRADAY,
            description=(
                "Identifies strong intraday momentum using rate of change, RSI, and ADX. "
                "Requires volume surge for entry confirmation. Uses ATR trailing stop."
            ),
            tags=["intraday", "momentum", "trend-following", "paper-only"],
            required_lookback=30,
        )

    def required_features(self) -> list[FeatureSpec]:
        return [
            FeatureSpec(name="rsi_14", params={"period": 14}),
            FeatureSpec(name="atr_14", params={"period": 14}),
            FeatureSpec(name="adx_14", params={"period": 14}),
            FeatureSpec(name="ema_12", params={"period": 12}),
            FeatureSpec(name="ema_26", params={"period": 26}),
            FeatureSpec(name="vwap_rolling", params={"period": 20}),
        ]

    def generate(self, context: MarketContext) -> RawSignal:
        bars = context.bars
        close = bars["close"]
        volume = bars["volume"]

        if len(bars) < 26:
            return RawSignal(
                state=SignalState.NO_SIGNAL, confidence=0,
                limitations=["Insufficient bars for momentum analysis"],
            )

        rsi = context.indicators.get("rsi_14")
        atr_14 = context.indicators.get("atr_14")
        adx = context.indicators.get("adx_14")
        ema_12 = context.indicators.get("ema_12")
        ema_26 = context.indicators.get("ema_26")
        vwap = context.indicators.get("vwap_rolling")

        curr_price = float(close.iloc[-1])
        curr_rsi = float(rsi.iloc[-1]) if rsi is not None and not rsi.isna().iloc[-1] else 50
        curr_atr = (
            float(atr_14.iloc[-1])
            if atr_14 is not None and not atr_14.isna().iloc[-1]
            else curr_price * 0.01
        )
        curr_adx = float(adx.iloc[-1]) if adx is not None and not adx.isna().iloc[-1] else 20
        curr_ema12 = float(ema_12.iloc[-1]) if ema_12 is not None and not ema_12.isna().iloc[-1] else curr_price
        curr_ema26 = float(ema_26.iloc[-1]) if ema_26 is not None and not ema_26.isna().iloc[-1] else curr_price
        curr_vwap = float(vwap.iloc[-1]) if vwap is not None and not vwap.isna().iloc[-1] else None

        # Rate of change (5-bar)
        roc_5 = (curr_price - float(close.iloc[-6])) / float(close.iloc[-6]) * 100 if len(close) >= 6 else 0

        # Volume surge
        avg_vol = float(volume.tail(20).mean()) if len(volume) >= 20 else float(volume.mean())
        curr_vol = float(volume.iloc[-1])
        vol_ratio = curr_vol / avg_vol if avg_vol > 0 else 1.0

        # EMA crossover
        ema_bullish = curr_ema12 > curr_ema26
        ema_cross_up = (
            float(ema_12.iloc[-2]) <= float(ema_26.iloc[-2])
            and curr_ema12 > curr_ema26
            if ema_12 is not None and ema_26 is not None and len(ema_12) >= 2
            else False
        )

        reason_codes = []
        limitations = []

        # Strong momentum entry
        if (
            roc_5 > 0.5
            and curr_rsi > 55 and curr_rsi < 80
            and curr_adx > 25
            and vol_ratio > 1.3
            and ema_bullish
        ):
            state = SignalState.ENTER_LONG
            confidence = 0.75
            reason_codes.append("strong_momentum")
            reason_codes.append("rsi_bullish")
            reason_codes.append("adx_trending")
            reason_codes.append("volume_surge")
            if curr_vwap and curr_price > curr_vwap:
                confidence = min(confidence + 0.05, 1.0)
                reason_codes.append("above_vwap")

        # EMA crossover with momentum
        elif ema_cross_up and vol_ratio > 1.2:
            state = SignalState.ENTER_LONG
            confidence = 0.65
            reason_codes.append("ema_crossover")
            reason_codes.append("volume_confirmation")
            if curr_adx > 20:
                confidence = min(confidence + 0.05, 1.0)
                reason_codes.append("adx_confirming")

        # Moderate momentum
        elif roc_5 > 0.3 and curr_rsi > 50 and ema_bullish:
            state = SignalState.HOLD
            confidence = 0.4
            reason_codes.append("moderate_momentum")
            limitations.append("No volume surge — weaker conviction")

        # Momentum fading
        elif roc_5 < -0.3 and curr_rsi < 45:
            state = SignalState.EXIT
            confidence = 0.55
            reason_codes.append("momentum_fading")
            reason_codes.append("rsi_weakening")

        # Overextended
        elif curr_rsi > 80:
            state = SignalState.REDUCE
            confidence = 0.5
            reason_codes.append("overextended_rsi")
            limitations.append("RSI overbought — pullback risk")

        else:
            state = SignalState.NO_SIGNAL
            confidence = 0.0

        entry_low = Decimal(str(round(curr_price - curr_atr * 0.5, 2)))
        entry_high = Decimal(str(round(curr_price + curr_atr * 0.3, 2)))

        return RawSignal(
            state=state,
            confidence=round(confidence, 4),
            entry_zone_low=entry_low if state == SignalState.ENTER_LONG else None,
            entry_zone_high=entry_high if state == SignalState.ENTER_LONG else None,
            invalidation_rule="Close below EMA(26) or RSI < 40" if state == SignalState.ENTER_LONG else "",
            invalidation_level=Decimal(str(round(curr_ema26, 2))) if state == SignalState.ENTER_LONG else None,
            target_method="risk_multiple",
            reason_codes=reason_codes,
            limitations=limitations,
        )

    def risk_plan(self, signal: RawSignal, portfolio_value: Decimal = Decimal("100000")) -> RiskPlan:
        if signal.state == SignalState.ENTER_LONG and signal.invalidation_level:
            entry_mid = (
                (signal.entry_zone_low + signal.entry_zone_high) / 2
                if signal.entry_zone_low and signal.entry_zone_high
                else Decimal("0")
            )
            stop = signal.invalidation_level
            risk_per_share = entry_mid - stop if entry_mid > stop else entry_mid * Decimal("0.01")
            return RiskPlan(
                max_loss_pct=Decimal("1.0"),
                suggested_size_pct=Decimal("3.0"),
                stop_loss=stop,
                take_profit=entry_mid + (risk_per_share * Decimal("2.5")) if risk_per_share > 0 else None,
            )
        return RiskPlan(max_loss_pct=Decimal("1.0"), suggested_size_pct=Decimal("3.0"))
