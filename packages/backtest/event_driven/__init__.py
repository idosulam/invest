"""Event-driven backtesting — PRD Section 6.

Deterministic event-driven simulation with configurable fills, fees,
latency and shared research/live semantics.
"""

from packages.backtest.event_driven.engine import EventDrivenBacktester

__all__ = ["EventDrivenBacktester"]
