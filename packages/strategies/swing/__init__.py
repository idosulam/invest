"""Swing strategies — import to register."""
from packages.strategies.swing.sma_crossover import SMACrossover
from packages.strategies.swing.rsi_reversion import RSIMeanReversion
from packages.strategies.swing.obv_trend import OBVTrend
from packages.strategies.swing.relative_strength_spy import RelativeStrengthSPY

__all__ = ["SMACrossover", "RSIMeanReversion", "OBVTrend", "RelativeStrengthSPY"]
