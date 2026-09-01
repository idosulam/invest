"""Opening Range Breakout (ORB) strategy — PRD Section 5.2 (Intraday).

Trades the breakout of the first 15-30 minute range.
Long when price breaks above OR high, short/exit when below OR low.
Paper trading only for MVP.
"""

from decimal import Decimal
from packages.strategies.registry.strategy_base import (
    Strategy, StrategyCard, FeatureSpec, MarketContext, RawSignal, RiskPlan,
    StrategyRegistry,
)
from packages.domain.enums.common import Horizon, SignalState


@StrategyRegistry.register
class OpeningRangeBreakout(Strategy):
    """Opening Range Breakout — trade the first 30-min range breakout."""

    @property
    def metadata(self) -> StrategyCard:
        return StrategyCard(
            name="Opening Range Breakout",
            version="1.0.0",
            horizon=Horizon.INTRADAY,
            description=(
                "Identifies the high/low of the first 30 minutes (6 × 5m bars). "
                "Enters long on breakout above OR high, exits on break below OR low. "
                "Uses volume confirmation and ATR-based stops."
            ),
            tags=["intraday", "breakout", "opening-range", "paper-only"],
            required_lookback=50,
        )

    def required_features(self) -> list[FeatureSpec]:
        return [
            FeatureSpec(name="atr_14", params={"period": 14}),
            FeatureSpec(name="vwap_rolling", params={"period": 20}),
            FeatureSpec(name="sma_20", params={"period": 20}),
        ]

    def generate(self, context: MarketContext) -> RawSignal:
        bars = context.bars
        close = bars["close"]
        high = context.bars["high"]
        low = context.bars["low"]
        volume = context.bars["volume"]

        if len(bars) < 20:
            return RawSignal(
                state=SignalState.NO_SIGNAL, confidence=0,
                limitations=["Insufficient intraday bars"],
            )

        atr_14 = context.indicators.get("atr_14")
        vwap = context.indicators.get("vwap_rolling")
        sma_20 = context.indicators.get("sma_20")

        curr_price = float(close.iloc[-1])
        curr_atr = (
            float(atr_14.iloc[-1])
            if atr_14 is not None and not atr_14.isna().iloc[-1]
            else curr_price * 0.01
        )

        # Estimate opening range: first 6 bars (30 min at 5m)
        or_bars = min(6, len(bars) // 3)
        if or_bars < 2:
            return RawSignal(
                state=SignalState.NO_SIGNAL, confidence=0,
                limitations=["Not enough bars for opening range"],
            )

        or_high = float(high.iloc[:or_bars].max())
        or_low = float(low.iloc[:or_bars].min())
        or_range = or_high - or_low

        if or_range <= 0:
            return RawSignal(
                state=SignalState.NO_SIGNAL, confidence=0,
                limitations=["Opening range is zero"],
            )

        # Current bar position relative to OR
        above_or_high = curr_price > or_high
        below_or_low = curr_price < or_low
        inside_or = not above_or_high and not below_or_low

        # Volume confirmation
        avg_vol = float(volume.iloc[:or_bars].mean()) if or_bars > 0 else 0
        curr_vol = float(volume.iloc[-1])
        vol_surge = curr_vol > avg_vol * 1.5 if avg_vol > 0 else False

        # VWAP confirmation
        curr_vwap = float(vwap.iloc[-1]) if vwap is not None and not vwap.isna().iloc[-1] else None

        reason_codes = []
        limitations = []

        if above_or_high and vol_surge:
            state = SignalState.ENTER_LONG
            confidence = 0.7
            reason_codes.append("or_breakout_above")
            reason_codes.append("volume_surge")
            if curr_vwap and curr_price > curr_vwap:
                confidence = min(confidence + 0.1, 1.0)
                reason_codes.append("above_vwap")
        elif above_or_high:
            state = SignalState.ENTER_LONG
            confidence = 0.55
            reason_codes.append("or_breakout_above")
            limitations.append("No volume confirmation — weaker signal")
        elif below_or_low and vol_surge:
            state = SignalState.EXIT
            confidence = 0.65
            reason_codes.append("or_breakdown")
            reason_codes.append("volume_surge")
        elif below_or_low:
            state = SignalState.WATCH
            confidence = 0.4
            reason_codes.append("or_breakdown_weak")
            limitations.append("Breakdown without volume — monitor")
        elif inside_or:
            state = SignalState.WATCH
            confidence = 0.2
            reason_codes.append("inside_opening_range")
            limitations.append("Price still inside opening range — wait for breakout")
        else:
            state = SignalState.NO_SIGNAL
            confidence = 0.0

        # Late-day penalty: reduce confidence if too close to close
        if len(bars) > 60:  # >5 hours of 5m bars
            if state == SignalState.ENTER_LONG:
                confidence = max(confidence - 0.15, 0.0)
                limitations.append("Late session — reduced conviction")

        entry_low = Decimal(str(round(or_high, 2)))
        entry_high = Decimal(str(round(or_high + curr_atr * 0.5, 2)))

        return RawSignal(
            state=state,
            confidence=round(confidence, 4),
            entry_zone_low=entry_low if state == SignalState.ENTER_LONG else None,
            entry_zone_high=entry_high if state == SignalState.ENTER_LONG else None,
            invalidation_rule="Close below opening range low" if state == SignalState.ENTER_LONG else "",
            invalidation_level=Decimal(str(round(or_low, 2))) if state == SignalState.ENTER_LONG else None,
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
                take_profit=entry_mid + (risk_per_share * Decimal("2")) if risk_per_share > 0 else None,
            )
        return RiskPlan(max_loss_pct=Decimal("1.0"), suggested_size_pct=Decimal("3.0"))
