"""Volatility Expansion strategy — PRD Section 5.2 (Intraday).

Trades volatility contraction → expansion breakouts.
Detects Bollinger Band squeeze (low bandwidth) then trades the expansion.
Paper trading only for MVP.
"""

from decimal import Decimal
from packages.strategies.registry.strategy_base import (
    Strategy, StrategyCard, FeatureSpec, MarketContext, RawSignal, RiskPlan,
    StrategyRegistry,
)
from packages.domain.enums.common import Horizon, SignalState


@StrategyRegistry.register
class VolatilityExpansion(Strategy):
    """Volatility Expansion — trade Bollinger Band squeeze breakouts."""

    @property
    def metadata(self) -> StrategyCard:
        return StrategyCard(
            name="Volatility Expansion",
            version="1.0.0",
            horizon=Horizon.INTRADAY,
            description=(
                "Detects Bollinger Band squeeze (low bandwidth) followed by expansion breakout. "
                "Uses Keltner Channels for squeeze detection and volume for confirmation."
            ),
            tags=["intraday", "volatility", "breakout", "squeeze", "paper-only"],
            required_lookback=30,
        )

    def required_features(self) -> list[FeatureSpec]:
        return [
            FeatureSpec(name="atr_14", params={"period": 14}),
            FeatureSpec(name="rsi_14", params={"period": 14}),
            FeatureSpec(name="sma_20", params={"period": 20}),
            FeatureSpec(name="bb_upper", params={"period": 20, "std_dev": 2.0}),
            FeatureSpec(name="bb_lower", params={"period": 20, "std_dev": 2.0}),
            FeatureSpec(name="bb_pct_b", params={"period": 20, "std_dev": 2.0}),
        ]

    def generate(self, context: MarketContext) -> RawSignal:
        bars = context.bars
        close = bars["close"]
        high = bars["high"]
        low = bars["low"]
        volume = bars["volume"]

        if len(bars) < 25:
            return RawSignal(
                state=SignalState.NO_SIGNAL, confidence=0,
                limitations=["Insufficient bars"],
            )

        atr_14 = context.indicators.get("atr_14")
        rsi = context.indicators.get("rsi_14")
        sma_20 = context.indicators.get("sma_20")
        bb_upper = context.indicators.get("bb_upper")
        bb_lower = context.indicators.get("bb_lower")
        bb_pct_b = context.indicators.get("bb_pct_b")

        curr_price = float(close.iloc[-1])
        curr_atr = (
            float(atr_14.iloc[-1])
            if atr_14 is not None and not atr_14.isna().iloc[-1]
            else curr_price * 0.01
        )
        curr_rsi = float(rsi.iloc[-1]) if rsi is not None and not rsi.isna().iloc[-1] else 50

        if bb_upper is None or bb_lower is None or bb_pct_b is None:
            return RawSignal(
                state=SignalState.NO_SIGNAL, confidence=0,
                limitations=["Bollinger Bands not available"],
            )

        curr_bb_upper = float(bb_upper.iloc[-1])
        curr_bb_lower = float(bb_lower.iloc[-1])
        curr_pct_b = float(bb_pct_b.iloc[-1])

        # Squeeze detection: bandwidth in bottom 20% of recent range
        bandwidth = (curr_bb_upper - curr_bb_lower) / curr_price if curr_price > 0 else 0
        recent_bw = []
        for i in range(-20, 0):
            try:
                bw = (float(bb_upper.iloc[i]) - float(bb_lower.iloc[i])) / float(close.iloc[i])
                recent_bw.append(bw)
            except (IndexError, ZeroDivisionError):
                pass

        if len(recent_bw) < 10:
            squeeze_active = False
        else:
            bw_min = min(recent_bw)
            bw_max = max(recent_bw)
            bw_range = bw_max - bw_min
            squeeze_active = bandwidth < bw_min + bw_range * 0.2 if bw_range > 0 else False

        # Expansion detection: bandwidth expanding after squeeze
        prev_bandwidth = (
            (float(bb_upper.iloc[-2]) - float(bb_lower.iloc[-2])) / float(close.iloc[-2])
            if len(close) >= 2 else 0
        )
        expanding = bandwidth > prev_bandwidth * 1.1

        # Volume surge
        avg_vol = float(volume.tail(20).mean()) if len(volume) >= 20 else float(volume.mean())
        curr_vol = float(volume.iloc[-1])
        vol_ratio = curr_vol / avg_vol if avg_vol > 0 else 1.0

        reason_codes = []
        limitations = []

        # Squeeze breakout — bullish
        if squeeze_active and expanding and curr_pct_b > 0.8 and vol_ratio > 1.3:
            state = SignalState.ENTER_LONG
            confidence = 0.7
            reason_codes.append("bb_squeeze_breakout")
            reason_codes.append("volatility_expansion")
            reason_codes.append("volume_surge")
            if curr_rsi > 50:
                confidence = min(confidence + 0.05, 1.0)
                reason_codes.append("rsi_confirming")

        # Squeeze breakout — bearish
        elif squeeze_active and expanding and curr_pct_b < 0.2 and vol_ratio > 1.3:
            state = SignalState.EXIT
            confidence = 0.65
            reason_codes.append("bb_squeeze_breakdown")
            reason_codes.append("volatility_expansion")

        # Expansion in progress — hold
        elif expanding and not squeeze_active:
            if curr_pct_b > 0.5:
                state = SignalState.HOLD
                confidence = 0.4
                reason_codes.append("expansion_continues")
            else:
                state = SignalState.WATCH
                confidence = 0.3
                reason_codes.append("expansion_weakening")
                limitations.append("Expansion may be fading")

        # Squeeze building — wait
        elif squeeze_active and not expanding:
            state = SignalState.WATCH
            confidence = 0.25
            reason_codes.append("squeeze_building")
            limitations.append("Volatility contracting — wait for expansion")

        # Overbought after expansion
        elif curr_pct_b > 1.0 and curr_rsi > 75:
            state = SignalState.REDUCE
            confidence = 0.5
            reason_codes.append("overbought_after_expansion")
            limitations.append("Price above upper band — pullback risk")

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
            invalidation_rule="Close below SMA(20)" if state == SignalState.ENTER_LONG else "",
            invalidation_level=Decimal(str(round(float(sma_20.iloc[-1]), 2))) if state == SignalState.ENTER_LONG and sma_20 is not None and not sma_20.isna().iloc[-1] else None,
            target_method="volatility_band",
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
                take_profit=entry_mid + (risk_per_share * Decimal("2")) if risk_per_share > 0 else None,
            )
        return RiskPlan(max_loss_pct=Decimal("1.0"), suggested_size_pct=Decimal("3.0"))
