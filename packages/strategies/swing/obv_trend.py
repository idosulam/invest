"""OBV Trend & Divergence strategy — swing horizon.

Uses On-Balance Volume (OBV) to confirm price trends and detect
divergences, which often precede reversals:

- Bullish confirmation: price and OBV both making higher highs.
- Bullish divergence: price makes a lower low while OBV makes a
  higher low (buying pressure building despite falling price).
- Bearish divergence: price makes a higher high while OBV makes a
  lower high (selling pressure building despite rising price) — exit
  signal for existing longs.
"""

from decimal import Decimal
from packages.strategies.registry.strategy_base import (
    Strategy, StrategyCard, FeatureSpec, MarketContext, RawSignal, RiskPlan,
    StrategyRegistry,
)
from packages.domain.enums.common import Horizon, SignalState


@StrategyRegistry.register
class OBVTrend(Strategy):
    """OBV-based trend confirmation and divergence detection."""

    LOOKBACK = 20  # bars used to find local highs/lows for divergence

    @property
    def metadata(self) -> StrategyCard:
        return StrategyCard(
            name="OBV Trend & Divergence",
            version="1.0.0",
            horizon=Horizon.SWING,
            description=(
                "Confirms price trends with On-Balance Volume and flags "
                "bullish/bearish divergences between price and volume flow."
            ),
            tags=["volume", "obv", "divergence", "swing"],
            required_lookback=40,
        )

    def required_features(self) -> list[FeatureSpec]:
        return [
            FeatureSpec(name="obv", params={}),
            FeatureSpec(name="sma_20", params={"period": 20}),
            FeatureSpec(name="atr_14", params={"period": 14}),
        ]

    def generate(self, context: MarketContext) -> RawSignal:
        close = context.bars["close"]
        obv = context.indicators.get("obv")
        sma_20 = context.indicators.get("sma_20")
        atr_14 = context.indicators.get("atr_14")

        if obv is None or len(close) < self.LOOKBACK + 5:
            return RawSignal(state=SignalState.NO_SIGNAL, confidence=0, limitations=["Insufficient data"])

        window_close = close.tail(self.LOOKBACK)
        window_obv = obv.tail(self.LOOKBACK)

        curr_price = float(close.iloc[-1])
        curr_atr = float(atr_14.iloc[-1]) if atr_14 is not None and not atr_14.isna().iloc[-1] else curr_price * 0.02
        curr_sma20 = float(sma_20.iloc[-1]) if sma_20 is not None and not sma_20.isna().iloc[-1] else None

        price_low_idx = window_close.idxmin()
        price_high_idx = window_close.idxmax()
        price_low = float(window_close.loc[price_low_idx])
        price_high = float(window_close.loc[price_high_idx])
        obv_at_price_low = float(window_obv.loc[price_low_idx])
        obv_at_price_high = float(window_obv.loc[price_high_idx])

        curr_obv = float(window_obv.iloc[-1])
        prev_price_recent = float(window_close.iloc[-2]) if len(window_close) >= 2 else curr_price

        third = max(len(window_obv) // 3, 1)
        obv_trend_up = float(window_obv.tail(third).mean()) > float(window_obv.head(third).mean())

        reason_codes = []
        limitations = []

        near_price_low = curr_price <= price_low * 1.02
        bullish_divergence = near_price_low and curr_obv > obv_at_price_low and curr_price < prev_price_recent * 1.0

        near_price_high = curr_price >= price_high * 0.98
        bearish_divergence = near_price_high and curr_obv < obv_at_price_high

        trend_confirmed = curr_sma20 is not None and curr_price > curr_sma20 and obv_trend_up

        if bullish_divergence:
            state = SignalState.ENTER_LONG
            confidence = 0.6
            reason_codes.append("obv_bullish_divergence")
            reason_codes.append("price_at_low_obv_rising")
        elif bearish_divergence:
            state = SignalState.EXIT
            confidence = 0.6
            reason_codes.append("obv_bearish_divergence")
            reason_codes.append("price_at_high_obv_falling")
        elif trend_confirmed:
            state = SignalState.HOLD
            confidence = 0.45
            reason_codes.append("obv_trend_confirmation")
        elif not obv_trend_up and curr_sma20 is not None and curr_price < curr_sma20:
            state = SignalState.WATCH
            confidence = 0.3
            reason_codes.append("obv_and_price_declining")
            limitations.append("Both price and volume flow weakening")
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
            invalidation_rule="Price closes below recent swing low with OBV confirming" if state == SignalState.ENTER_LONG else "",
            invalidation_level=Decimal(str(round(price_low - curr_atr, 2))) if state == SignalState.ENTER_LONG else None,
            target_method="volatility_band",
            reason_codes=reason_codes,
            limitations=limitations,
        )

    def risk_plan(self, signal: RawSignal, portfolio_value: Decimal = Decimal("100000")) -> RiskPlan:
        return RiskPlan(
            max_loss_pct=Decimal("2.0"),
            suggested_size_pct=Decimal("4.0"),
            stop_loss=signal.invalidation_level,
        )
