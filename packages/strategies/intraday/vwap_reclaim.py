"""VWAP Reclaim/Rejection strategy — PRD Section 5.2 (Intraday).

Trades when price reclaims VWAP from below (long) or rejects from above (exit).
VWAP is the institutional reference line — reclaim = bullish, rejection = bearish.
Paper trading only for MVP.
"""

from decimal import Decimal
from packages.strategies.registry.strategy_base import (
    Strategy, StrategyCard, FeatureSpec, MarketContext, RawSignal, RiskPlan,
    StrategyRegistry,
)
from packages.domain.enums.common import Horizon, SignalState


@StrategyRegistry.register
class VWAPReclaimRejection(Strategy):
    """VWAP Reclaim/Rejection — trade institutional reference line reactions."""

    @property
    def metadata(self) -> StrategyCard:
        return StrategyCard(
            name="VWAP Reclaim/Rejection",
            version="1.0.0",
            horizon=Horizon.INTRADAY,
            description=(
                "Enters long when price reclaims VWAP from below with volume confirmation. "
                "Exits when price rejects VWAP from above. Uses RSI and ATR for confirmation."
            ),
            tags=["intraday", "vwap", "mean-reversion", "paper-only"],
            required_lookback=30,
        )

    def required_features(self) -> list[FeatureSpec]:
        return [
            FeatureSpec(name="vwap_rolling", params={"period": 20}),
            FeatureSpec(name="rsi_14", params={"period": 14}),
            FeatureSpec(name="atr_14", params={"period": 14}),
            FeatureSpec(name="sma_20", params={"period": 20}),
        ]

    def generate(self, context: MarketContext) -> RawSignal:
        bars = context.bars
        close = bars["close"]
        volume = bars["volume"]

        if len(bars) < 15:
            return RawSignal(
                state=SignalState.NO_SIGNAL, confidence=0,
                limitations=["Insufficient bars"],
            )

        vwap = context.indicators.get("vwap_rolling")
        rsi = context.indicators.get("rsi_14")
        atr_14 = context.indicators.get("atr_14")
        sma_20 = context.indicators.get("sma_20")

        if vwap is None or vwap.isna().iloc[-1]:
            return RawSignal(
                state=SignalState.NO_SIGNAL, confidence=0,
                limitations=["VWAP not available"],
            )

        curr_price = float(close.iloc[-1])
        prev_price = float(close.iloc[-2])
        curr_vwap = float(vwap.iloc[-1])
        prev_vwap = float(vwap.iloc[-2])
        curr_rsi = float(rsi.iloc[-1]) if rsi is not None and not rsi.isna().iloc[-1] else 50
        curr_atr = (
            float(atr_14.iloc[-1])
            if atr_14 is not None and not atr_14.isna().iloc[-1]
            else curr_price * 0.01
        )

        # Volume analysis
        avg_vol = float(volume.tail(20).mean()) if len(volume) >= 20 else float(volume.mean())
        curr_vol = float(volume.iloc[-1])
        vol_ratio = curr_vol / avg_vol if avg_vol > 0 else 1.0

        # VWAP cross detection
        crossed_above = prev_price <= prev_vwap and curr_price > curr_vwap
        crossed_below = prev_price >= prev_vwap and curr_price < curr_vwap
        above_vwap = curr_price > curr_vwap
        below_vwap = curr_price < curr_vwap

        # Distance from VWAP (normalized by ATR)
        vwap_distance = abs(curr_price - curr_vwap) / curr_atr if curr_atr > 0 else 0

        reason_codes = []
        limitations = []

        # VWAP Reclaim: price crosses above VWAP from below
        if crossed_above and vol_ratio > 1.2:
            state = SignalState.ENTER_LONG
            confidence = 0.7
            reason_codes.append("vwap_reclaim")
            reason_codes.append("volume_confirmation")
            if curr_rsi > 40 and curr_rsi < 70:
                confidence = min(confidence + 0.05, 1.0)
                reason_codes.append("rsi_supportive")
        elif crossed_above:
            state = SignalState.ENTER_LONG
            confidence = 0.55
            reason_codes.append("vwap_reclaim")
            limitations.append("Weak volume — lower conviction")

        # VWAP Rejection: price crosses below VWAP from above
        elif crossed_below and vol_ratio > 1.2:
            state = SignalState.EXIT
            confidence = 0.65
            reason_codes.append("vwap_rejection")
            reason_codes.append("volume_confirmation")
        elif crossed_below:
            state = SignalState.REDUCE
            confidence = 0.5
            reason_codes.append("vwap_rejection")
            limitations.append("Weak volume on rejection")

        # Holding above VWAP with momentum
        elif above_vwap and curr_rsi > 50 and vwap_distance < 1.5:
            state = SignalState.HOLD
            confidence = 0.4
            reason_codes.append("above_vwap_holding")

        # Extended above VWAP — pullback risk
        elif above_vwap and vwap_distance > 2.0:
            state = SignalState.WATCH
            confidence = 0.3
            reason_codes.append("extended_above_vwap")
            limitations.append("Price extended from VWAP — mean reversion risk")

        # Below VWAP — no long signal
        elif below_vwap and curr_rsi < 40:
            state = SignalState.WATCH
            confidence = 0.25
            reason_codes.append("below_vwap_weak")
            limitations.append("Price below VWAP with weak RSI — wait for reclaim")

        else:
            state = SignalState.NO_SIGNAL
            confidence = 0.0

        entry_low = Decimal(str(round(curr_vwap - curr_atr * 0.3, 2)))
        entry_high = Decimal(str(round(curr_vwap + curr_atr * 0.3, 2)))

        return RawSignal(
            state=state,
            confidence=round(confidence, 4),
            entry_zone_low=entry_low if state == SignalState.ENTER_LONG else None,
            entry_zone_high=entry_high if state == SignalState.ENTER_LONG else None,
            invalidation_rule="Close below VWAP" if state == SignalState.ENTER_LONG else "",
            invalidation_level=Decimal(str(round(curr_vwap - curr_atr, 2))) if state == SignalState.ENTER_LONG else None,
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
