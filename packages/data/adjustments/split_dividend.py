"""Corporate action adjustments — PRD Section 4.3 step 5.

Applies split and dividend adjustments through versioned corporate-action records.
Maintains both raw and adjusted values.
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional

from packages.data.providers.base import Bar, CorporateActionRecord
from packages.domain.enums.common import CorporateActionType

logger = logging.getLogger(__name__)


@dataclass
class AdjustmentResult:
    """Result of applying adjustments to a bar series."""
    bars: list[Bar]
    adjustment_factor: Decimal
    actions_applied: list[CorporateActionRecord]


class CorporateActionAdjuster:
    """Applies corporate action adjustments to OHLCV data.

    Maintains both raw and adjusted values per the PRD canonical bar model.
    """

    def __init__(self, precision: int = 10):
        self._precision = precision

    def adjust_bars(
        self,
        bars: list[Bar],
        actions: list[CorporateActionRecord],
        adjust_from: Optional[datetime] = None,
    ) -> AdjustmentResult:
        """Apply corporate action adjustments to a series of bars.

        Adjustments are applied backwards from the most recent bar:
        - Splits: multiply/divide prices by the split factor
        - Dividends: adjust prices by the dividend yield

        Args:
            bars: Sorted list of OHLCV bars (oldest first)
            actions: Corporate actions to apply
            adjust_from: If set, only adjust bars before this date
        """
        if not bars or not actions:
            return AdjustmentResult(
                bars=bars,
                adjustment_factor=Decimal("1.0"),
                actions_applied=[],
            )

        # Sort bars by timestamp
        sorted_bars = sorted(bars, key=lambda b: b.ts_open)
        # Sort actions by ex-date (newest first for backward adjustment)
        sorted_actions = sorted(
            actions,
            key=lambda a: a.ex_date,
            reverse=True,
        )

        # Calculate cumulative adjustment factor for each bar
        adjusted_bars = []
        actions_applied = []

        for bar in sorted_bars:
            cumulative_factor = Decimal("1.0")

            for action in sorted_actions:
                # Only apply actions that occurred after this bar
                if action.ex_date <= bar.ts_open:
                    continue

                if action.type == CorporateActionType.SPLIT and action.factor:
                    cumulative_factor *= action.factor
                    if action not in actions_applied:
                        actions_applied.append(action)

                elif action.type == CorporateActionType.DIVIDEND and action.cash_amount:
                    # Dividend adjustment: price_adj = price * (1 - div/close)
                    # For backward adjustment, we need the close at ex-date
                    # Simplified: use the bar's close as approximation
                    if bar.close > Decimal("0"):
                        div_yield = action.cash_amount / bar.close
                        cumulative_factor *= (Decimal("1.0") - div_yield)
                        if action not in actions_applied:
                            actions_applied.append(action)

            # Apply adjustment
            if cumulative_factor != Decimal("1.0"):
                adjusted_bar = Bar(
                    symbol=bar.symbol,
                    timeframe=bar.timeframe,
                    ts_open=bar.ts_open,
                    ts_close=bar.ts_close,
                    open=self._adjust_price(bar.open, cumulative_factor),
                    high=self._adjust_price(bar.high, cumulative_factor),
                    low=self._adjust_price(bar.low, cumulative_factor),
                    close=self._adjust_price(bar.close, cumulative_factor),
                    volume=self._adjust_volume(bar.volume, cumulative_factor),
                    vwap=self._adjust_price(bar.vwap, cumulative_factor) if bar.vwap else None,
                    trade_count=bar.trade_count,
                    currency=bar.currency,
                )
                adjusted_bars.append(adjusted_bar)
            else:
                adjusted_bars.append(bar)

        return AdjustmentResult(
            bars=adjusted_bars,
            adjustment_factor=Decimal("1.0"),  # Per-bar factor varies
            actions_applied=actions_applied,
        )

    def calculate_split_factor(self, ratio: str) -> Decimal:
        """Calculate adjustment factor from a split ratio like '2:1' or '3:2'.

        '2:1' means each old share becomes 2 new shares → factor = 2.0
        '3:2' means each 2 old shares become 3 new shares → factor = 1.5
        """
        try:
            parts = ratio.replace(":", "/").split("/")
            if len(parts) == 2:
                new = Decimal(parts[0].strip())
                old = Decimal(parts[1].strip())
                if old > Decimal("0"):
                    return (new / old).quantize(
                        Decimal(10) ** -self._precision,
                        rounding=ROUND_HALF_UP,
                    )
        except Exception as e:
            logger.error(f"Error parsing split ratio '{ratio}': {e}")
        return Decimal("1.0")

    def _adjust_price(self, price: Optional[Decimal], factor: Decimal) -> Optional[Decimal]:
        """Apply adjustment factor to a price."""
        if price is None:
            return None
        return (price * factor).quantize(
            Decimal(10) ** -self._precision,
            rounding=ROUND_HALF_UP,
        )

    def _adjust_volume(self, volume: Decimal, factor: Decimal) -> Decimal:
        """Apply inverse adjustment factor to volume.

        When prices are adjusted up by factor, volume is adjusted down.
        """
        if factor == Decimal("0"):
            return volume
        return (volume / factor).quantize(
            Decimal("0.01"),
            rounding=ROUND_HALF_UP,
        )
