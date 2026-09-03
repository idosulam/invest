"""Relative Strength vs SPY strategy — PRD Section 5.2 (Swing).

Compares a stock's rolling return against SPY's rolling return.
Stocks outperforming the benchmark tend to continue outperforming
(momentum persistence). This is a genuinely different signal type
from all other strategies, which only look at a stock in isolation.
"""

from decimal import Decimal
from packages.strategies.registry.strategy_base import (
    Strategy, StrategyCard, FeatureSpec, MarketContext, RawSignal, RiskPlan,
    StrategyRegistry,
)
from packages.domain.enums.common import Horizon, SignalState


@StrategyRegistry.register
class RelativeStrengthSPY(Strategy):
    """Relative Strength vs SPY — buy outperformers, exit underperformers."""

    @property
    def metadata(self) -> StrategyCard:
        return StrategyCard(
            name="Relative Strength vs SPY",
            version="1.0.0",
            horizon=Horizon.SWING,
            description=(
                "Compares the stock's rolling return against SPY over 20 and 60 day "
                "windows. Enters long when the stock is outperforming the benchmark "
                "with accelerating relative strength. Exits when relative strength "
                "fades and the stock starts underperforming SPY."
            ),
            tags=["relative-strength", "benchmark", "momentum", "swing"],
            required_lookback=65,
        )

    def required_features(self) -> list[FeatureSpec]:
        return [
            FeatureSpec(name="sma_20", params={"period": 20}),
            FeatureSpec(name="atr_14", params={"period": 14}),
            FeatureSpec(name="rsi_14", params={"period": 14}),
        ]

    def generate(self, context: MarketContext) -> RawSignal:
        close = context.bars["close"]
        benchmark = context.benchmark_bars

        if benchmark is None or benchmark.empty:
            return RawSignal(
                state=SignalState.NO_SIGNAL,
                confidence=0,
                limitations=["No benchmark (SPY) data available — cannot compute relative strength"],
            )

        if len(close) < 65 or len(benchmark) < 65:
            return RawSignal(
                state=SignalState.NO_SIGNAL,
                confidence=0,
                limitations=["Need at least 65 bars for both stock and benchmark"],
            )

        sma_20 = context.indicators.get("sma_20")
        atr_14 = context.indicators.get("atr_14")
        rsi_14 = context.indicators.get("rsi_14")

        curr_price = float(close.iloc[-1])
        curr_atr = (
            float(atr_14.iloc[-1])
            if atr_14 is not None and not atr_14.isna().iloc[-1]
            else curr_price * 0.02
        )
        curr_rsi = (
            float(rsi_14.iloc[-1])
            if rsi_14 is not None and not rsi_14.isna().iloc[-1]
            else 50
        )

        # Align benchmark to stock dates (use last N bars)
        bench_close = benchmark["close"].iloc[-len(close):].reset_index(drop=True)
        stock_close = close.reset_index(drop=True)

        # Rolling returns
        stock_ret_20 = (stock_close.iloc[-1] / stock_close.iloc[-21] - 1) * 100
        bench_ret_20 = (bench_close.iloc[-1] / bench_close.iloc[-21] - 1) * 100
        stock_ret_60 = (stock_close.iloc[-1] / stock_close.iloc[-61] - 1) * 100
        bench_ret_60 = (bench_close.iloc[-1] / bench_close.iloc[-61] - 1) * 100

        # Relative strength = stock return - benchmark return
        rs_20 = stock_ret_20 - bench_ret_20
        rs_60 = stock_ret_60 - bench_ret_60

        # Previous values for trend detection
        stock_ret_20_prev = (stock_close.iloc[-2] / stock_close.iloc[-22] - 1) * 100
        bench_ret_20_prev = (bench_close.iloc[-2] / bench_close.iloc[-22] - 1) * 100
        rs_20_prev = stock_ret_20_prev - bench_ret_20_prev

        # RS accelerating: current RS > previous RS
        rs_accelerating = rs_20 > rs_20_prev

        # Price above SMA(20) for trend confirmation
        above_sma = (
            curr_price > float(sma_20.iloc[-1])
            if sma_20 is not None and not sma_20.isna().iloc[-1]
            else True
        )

        reason_codes = []
        limitations = []

        # Strong outperformance on both timeframes
        if rs_20 > 3 and rs_60 > 5 and rs_accelerating and above_sma:
            state = SignalState.ENTER_LONG
            confidence = 0.75
            reason_codes.append("strong_outperformance")
            reason_codes.append("rs_accelerating")
            reason_codes.append("above_sma20")
            if curr_rsi > 50 and curr_rsi < 80:
                confidence = min(confidence + 0.05, 1.0)
                reason_codes.append("rsi_supportive")

        # Moderate outperformance with acceleration
        elif rs_20 > 1 and rs_accelerating and above_sma:
            state = SignalState.ENTER_LONG
            confidence = 0.6
            reason_codes.append("moderate_outperformance")
            reason_codes.append("rs_accelerating")
            limitations.append("60-day relative strength weaker — shorter-term play")

        # Outperforming but RS fading
        elif rs_20 > 0 and not rs_accelerating and rs_60 > 3:
            state = SignalState.HOLD
            confidence = 0.45
            reason_codes.append("outperforming_but_fading")
            limitations.append("Relative strength decelerating — monitor for exit")

        # Underperforming on both timeframes
        elif rs_20 < -2 and rs_60 < -3:
            state = SignalState.EXIT
            confidence = 0.65
            reason_codes.append("underperforming_benchmark")
            reason_codes.append("rs_deteriorating")

        # Slight underperformance
        elif rs_20 < 0:
            state = SignalState.WATCH
            confidence = 0.3
            reason_codes.append("slight_underperformance")
            limitations.append("Stock lagging benchmark — wait for RS reversal")

        else:
            state = SignalState.NO_SIGNAL
            confidence = 0.0

        entry_low = Decimal(str(round(curr_price - curr_atr, 2)))
        entry_high = Decimal(str(round(curr_price + curr_atr * 0.5, 2)))

        return RawSignal(
            state=state,
            confidence=round(confidence, 4),
            entry_zone_low=entry_low if state == SignalState.ENTER_LONG else None,
            entry_zone_high=entry_high if state == SignalState.ENTER_LONG else None,
            invalidation_rule="Close below SMA(20) or RS turns negative" if state == SignalState.ENTER_LONG else "",
            invalidation_level=Decimal(str(round(float(sma_20.iloc[-1]), 2)))
            if state == SignalState.ENTER_LONG and sma_20 is not None and not sma_20.isna().iloc[-1]
            else None,
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
            risk_per_share = entry_mid - stop if entry_mid > stop else entry_mid * Decimal("0.02")
            return RiskPlan(
                max_loss_pct=Decimal("2.0"),
                suggested_size_pct=Decimal("5.0"),
                stop_loss=stop,
                take_profit=entry_mid + (risk_per_share * Decimal("3")) if risk_per_share > 0 else None,
            )
        return RiskPlan()
