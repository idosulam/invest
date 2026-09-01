"""Strategies package — imports all strategies to trigger registration."""

from packages.strategies.swing import sma_crossover, rsi_reversion
from packages.strategies.long_term import quality_value
from packages.strategies.intraday import (
    opening_range_breakout,
    vwap_reclaim,
    intraday_momentum,
    volatility_expansion,
)
