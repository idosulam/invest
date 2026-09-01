"""Unit tests for backtesting engines — PRD Section 6."""

import numpy as np
import pandas as pd
import pytest

from packages.backtest.event_driven.engine import (
    EventDrivenBacktester, BacktestConfig, BacktestResult, Trade,
)


def make_bars(n: int = 200) -> pd.DataFrame:
    """Generate test bar data."""
    np.random.seed(42)
    close = 100 + np.cumsum(np.random.randn(n) * 0.5)
    return pd.DataFrame({
        "ts_open": pd.date_range("2024-01-01", periods=n, freq="D"),
        "open": close + np.random.randn(n) * 0.1,
        "high": close + abs(np.random.randn(n) * 0.5),
        "low": close - abs(np.random.randn(n) * 0.5),
        "close": close,
        "volume": np.random.randint(100000, 1000000, n),
    })


class TestEventDrivenBacktester:
    """Test event-driven backtest engine."""

    def test_basic_run(self):
        bars = make_bars(200)

        def signal_fn(df, idx):
            if idx < 20:
                return None
            if idx % 20 == 0:
                return "BUY"
            if idx % 20 == 10:
                return "SELL"
            return None

        bt = EventDrivenBacktester()
        result = bt.run(bars, signal_fn)

        assert isinstance(result, BacktestResult)
        assert result.metrics is not None
        assert result.equity_curve is not None
        assert result.drawdown_curve is not None

    def test_no_signals(self):
        bars = make_bars(100)

        def signal_fn(df, idx):
            return None

        bt = EventDrivenBacktester()
        result = bt.run(bars, signal_fn)
        assert result.metrics.total_trades == 0

    def test_commission_applied(self):
        bars = make_bars(100)

        def signal_fn(df, idx):
            if idx == 10:
                return "BUY"
            if idx == 50:
                return "SELL"
            return None

        config = BacktestConfig(commission_pct=0.01)  # 1% commission
        bt = EventDrivenBacktester(config)
        result = bt.run(bars, signal_fn)
        assert result.metrics.total_commission > 0

    def test_slippage_applied(self):
        bars = make_bars(100)

        def signal_fn(df, idx):
            if idx == 10:
                return "BUY"
            if idx == 50:
                return "SELL"
            return None

        config = BacktestConfig(slippage_pct=0.01)  # 1% slippage
        bt = EventDrivenBacktester(config)
        result = bt.run(bars, signal_fn)
        assert result.metrics.total_slippage > 0

    def test_metrics_completeness(self):
        bars = make_bars(200)

        def signal_fn(df, idx):
            if idx < 20:
                return None
            if idx % 30 == 0:
                return "BUY"
            if idx % 30 == 15:
                return "SELL"
            return None

        bt = EventDrivenBacktester()
        result = bt.run(bars, signal_fn)

        metrics = result.metrics
        assert hasattr(metrics, "total_return")
        assert hasattr(metrics, "annualized_return")
        assert hasattr(metrics, "volatility")
        assert hasattr(metrics, "sharpe_ratio")
        assert hasattr(metrics, "sortino_ratio")
        assert hasattr(metrics, "max_drawdown")
        assert hasattr(metrics, "calmar_ratio")
        assert hasattr(metrics, "win_rate")
        assert hasattr(metrics, "payoff_ratio")
        assert hasattr(metrics, "total_trades")
        assert hasattr(metrics, "total_commission")
        assert hasattr(metrics, "total_slippage")
        assert hasattr(metrics, "exposure")
        assert hasattr(metrics, "turnover")
        assert hasattr(metrics, "profit_factor")
        assert hasattr(metrics, "max_consecutive_losses")
        assert hasattr(metrics, "benchmark_return")
        assert hasattr(metrics, "alpha")
        assert hasattr(metrics, "beta")

    def test_empty_bars(self):
        bars = pd.DataFrame()
        bt = EventDrivenBacktester()
        result = bt.run(bars, lambda df, idx: None)
        assert result.metrics.total_trades == 0

    def test_fill_delay(self):
        bars = make_bars(100)

        def signal_fn(df, idx):
            if idx == 10:
                return "BUY"
            if idx == 50:
                return "SELL"
            return None

        config = BacktestConfig(fill_delay_bars=1)
        bt = EventDrivenBacktester(config)
        result = bt.run(bars, signal_fn)
        # With delay, entry should be at bar 11, not 10
        if result.trades:
            assert result.trades[0].bars_held > 0
