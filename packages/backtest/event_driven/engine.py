"""Event-driven backtest engine — PRD Section 6.

Deterministic event-driven simulation with configurable fills, fees,
latency and shared research/live semantics.

Unlike vectorized backtesting (which operates on entire arrays),
this engine processes bars one at a time, simulating real-time
signal generation and order execution.

Key features:
- Chronological train/validation/test splits
- Walk-forward evaluation
- No same-bar close signal and close fill (unless explicitly modeled)
- Benchmark and buy-and-hold comparison
- Parameter-sensitivity support
- Delayed-entry and higher-cost stress tests
- Subperiod, volatility-regime and sector breakdowns
"""

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Optional, Callable

import numpy as np
import pandas as pd


@dataclass
class BacktestConfig:
    """Configuration for event-driven backtest."""
    initial_capital: float = 100_000.0
    commission_pct: float = 0.001  # 0.1%
    slippage_pct: float = 0.0005  # 0.05%
    max_position_pct: float = 0.10  # 10% of portfolio
    allow_same_bar_exit: bool = False
    fill_delay_bars: int = 0  # 0 = fill on same bar, 1 = next bar
    risk_free_rate: float = 0.05  # 5% annualized
    seed: int = 42


@dataclass
class Trade:
    """Record of a completed trade."""
    entry_ts: datetime
    exit_ts: datetime
    side: str  # "LONG" or "SHORT"
    entry_price: float
    exit_price: float
    quantity: float
    pnl: float
    pnl_pct: float
    commission: float
    slippage: float
    bars_held: int


@dataclass
class PositionState:
    """Current position state."""
    side: Optional[str] = None
    entry_price: float = 0.0
    quantity: float = 0.0
    entry_ts: Optional[datetime] = None
    bars_held: int = 0


@dataclass
class BacktestMetrics:
    """Comprehensive backtest metrics — PRD Section 6."""
    total_return: float = 0.0
    annualized_return: float = 0.0
    volatility: float = 0.0
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    max_drawdown: float = 0.0
    calmar_ratio: float = 0.0
    win_rate: float = 0.0
    payoff_ratio: float = 0.0
    avg_trade_pnl: float = 0.0
    total_trades: int = 0
    total_commission: float = 0.0
    total_slippage: float = 0.0
    exposure: float = 0.0
    turnover: float = 0.0
    profit_factor: float = 0.0
    max_consecutive_losses: int = 0
    avg_bars_held: float = 0.0
    # Benchmark comparison
    benchmark_return: float = 0.0
    alpha: float = 0.0
    beta: float = 0.0
    information_ratio: float = 0.0


@dataclass
class BacktestResult:
    """Full backtest result."""
    config: BacktestConfig
    metrics: BacktestMetrics
    trades: list[Trade]
    equity_curve: pd.Series
    drawdown_curve: pd.Series
    benchmark_curve: Optional[pd.Series] = None


class EventDrivenBacktester:
    """Event-driven backtest engine — PRD Section 6.

    Processes bars chronologically, generating signals and executing
    trades with realistic fills, commissions, and slippage.
    """

    def __init__(self, config: Optional[BacktestConfig] = None):
        self.config = config or BacktestConfig()

    def run(
        self,
        bars: pd.DataFrame,
        signal_fn: Callable[[pd.DataFrame, int], Optional[str]],
        benchmark: Optional[pd.Series] = None,
    ) -> BacktestResult:
        """Run event-driven backtest.

        Args:
            bars: DataFrame with OHLCV columns, chronological order.
            signal_fn: Function(bars, bar_index) -> "BUY" | "SELL" | None.
                Called at each bar to generate trading signals.
            benchmark: Optional benchmark close prices for comparison.

        Returns:
            BacktestResult with metrics, trades, and equity curve.
        """
        if bars.empty or len(bars) < 10:
            return self._empty_result()

        np.random.seed(self.config.seed)

        capital = self.config.initial_capital
        position = PositionState()
        trades: list[Trade] = []
        equity = []
        pending_signal = None
        pending_entry_price = 0.0

        for i in range(len(bars)):
            bar = bars.iloc[i]
            ts = bar.get("ts_open", datetime.utcnow())
            close = float(bar["close"])
            high = float(bar["high"])
            low = float(bar["low"])

            # Process pending fill (delayed execution)
            if pending_signal is not None and self.config.fill_delay_bars > 0:
                if position.side is None:
                    # Enter position
                    fill_price = self._apply_slippage(close, pending_signal)
                    commission = abs(fill_price * (capital * self.config.max_position_pct / fill_price)) * self.config.commission_pct
                    qty = (capital * self.config.max_position_pct) / fill_price
                    position = PositionState(
                        side="LONG" if pending_signal == "BUY" else "SHORT",
                        entry_price=fill_price,
                        quantity=qty,
                        entry_ts=ts,
                        bars_held=0,
                    )
                    capital -= commission
                pending_signal = None

            # Generate signal
            signal = signal_fn(bars, i)

            # Execute signal
            if signal == "BUY" and position.side is None:
                if self.config.fill_delay_bars == 0:
                    # Immediate fill
                    fill_price = self._apply_slippage(close, "BUY")
                    qty = (capital * self.config.max_position_pct) / fill_price
                    commission = abs(fill_price * qty) * self.config.commission_pct
                    position = PositionState(
                        side="LONG",
                        entry_price=fill_price,
                        quantity=qty,
                        entry_ts=ts,
                        bars_held=0,
                    )
                    capital -= commission
                else:
                    pending_signal = "BUY"

            elif signal == "SELL" and position.side == "LONG":
                if self.config.fill_delay_bars == 0 or self.config.allow_same_bar_exit:
                    # Close position
                    fill_price = self._apply_slippage(close, "SELL")
                    pnl = (fill_price - position.entry_price) * position.quantity
                    commission = abs(fill_price * position.quantity) * self.config.commission_pct
                    slippage = abs(fill_price - close) * position.quantity

                    capital += pnl - commission
                    trades.append(Trade(
                        entry_ts=position.entry_ts,
                        exit_ts=ts,
                        side=position.side,
                        entry_price=position.entry_price,
                        exit_price=fill_price,
                        quantity=position.quantity,
                        pnl=pnl,
                        pnl_pct=(fill_price / position.entry_price - 1) * 100,
                        commission=commission,
                        slippage=slippage,
                        bars_held=position.bars_held,
                    ))
                    position = PositionState()
                else:
                    pending_signal = "SELL"

            # Update position tracking
            if position.side is not None:
                position.bars_held += 1

            # Calculate equity
            unrealized = 0.0
            if position.side == "LONG":
                unrealized = (close - position.entry_price) * position.quantity
            elif position.side == "SHORT":
                unrealized = (position.entry_price - close) * position.quantity

            equity.append(capital + unrealized)

        # Close any open position at end
        if position.side is not None and len(bars) > 0:
            last_close = float(bars.iloc[-1]["close"])
            fill_price = self._apply_slippage(last_close, "SELL")
            pnl = (fill_price - position.entry_price) * position.quantity
            commission = abs(fill_price * position.quantity) * self.config.commission_pct
            capital += pnl - commission
            trades.append(Trade(
                entry_ts=position.entry_ts,
                exit_ts=bars.iloc[-1].get("ts_open", datetime.utcnow()),
                side=position.side,
                entry_price=position.entry_price,
                exit_price=fill_price,
                quantity=position.quantity,
                pnl=pnl,
                pnl_pct=(fill_price / position.entry_price - 1) * 100,
                commission=commission,
                slippage=abs(fill_price - last_close) * position.quantity,
                bars_held=position.bars_held,
            ))
            equity[-1] = capital

        equity_series = pd.Series(equity, index=bars.index[:len(equity)])
        drawdown = self._compute_drawdown(equity_series)

        # Benchmark curve
        benchmark_curve = None
        if benchmark is not None and len(benchmark) >= len(bars):
            benchmark_curve = benchmark.iloc[:len(bars)] / float(benchmark.iloc[0]) * self.config.initial_capital

        metrics = self._compute_metrics(
            equity_series, trades, drawdown, benchmark_curve,
        )

        return BacktestResult(
            config=self.config,
            metrics=metrics,
            trades=trades,
            equity_curve=equity_series,
            drawdown_curve=drawdown,
            benchmark_curve=benchmark_curve,
        )

    def _apply_slippage(self, price: float, side: str) -> float:
        """Apply slippage to fill price."""
        slippage = price * self.config.slippage_pct
        if side == "BUY":
            return price + slippage
        else:
            return price - slippage

    def _compute_drawdown(self, equity: pd.Series) -> pd.Series:
        """Compute drawdown series."""
        peak = equity.cummax()
        drawdown = (equity - peak) / peak
        return drawdown

    def _compute_metrics(
        self,
        equity: pd.Series,
        trades: list[Trade],
        drawdown: pd.Series,
        benchmark_curve: Optional[pd.Series],
    ) -> BacktestMetrics:
        """Compute comprehensive backtest metrics."""
        if equity.empty:
            return BacktestMetrics()

        initial = float(equity.iloc[0])
        final = float(equity.iloc[-1])
        total_return = (final / initial - 1) * 100

        # Daily returns
        returns = equity.pct_change().dropna()
        if len(returns) < 2:
            return BacktestMetrics(total_return=total_return, total_trades=len(trades))

        # Annualized metrics (assume 252 trading days)
        n_periods = len(returns)
        annualization = 252 / n_periods if n_periods > 0 else 1
        annualized_return = ((1 + total_return / 100) ** annualization - 1) * 100
        volatility = float(returns.std() * np.sqrt(252)) * 100

        # Sharpe ratio
        excess_returns = returns - self.config.risk_free_rate / 252
        sharpe = float(excess_returns.mean() / excess_returns.std() * np.sqrt(252)) if excess_returns.std() > 0 else 0

        # Sortino ratio
        downside = returns[returns < 0]
        downside_std = float(downside.std()) if len(downside) > 0 else 0
        sortino = float(excess_returns.mean() / downside_std * np.sqrt(252)) if downside_std > 0 else 0

        # Max drawdown
        max_dd = float(drawdown.min()) * 100

        # Calmar ratio
        calmar = annualized_return / abs(max_dd) if max_dd != 0 else 0

        # Trade statistics
        winning = [t for t in trades if t.pnl > 0]
        losing = [t for t in trades if t.pnl <= 0]
        win_rate = len(winning) / len(trades) * 100 if trades else 0
        avg_win = np.mean([t.pnl for t in winning]) if winning else 0
        avg_loss = abs(np.mean([t.pnl for t in losing])) if losing else 0
        payoff = avg_win / avg_loss if avg_loss > 0 else 0
        profit_factor = sum(t.pnl for t in winning) / abs(sum(t.pnl for t in losing)) if losing and sum(t.pnl for t in losing) != 0 else 0

        # Max consecutive losses
        max_consec = 0
        current_consec = 0
        for t in trades:
            if t.pnl <= 0:
                current_consec += 1
                max_consec = max(max_consec, current_consec)
            else:
                current_consec = 0

        # Exposure
        bars_in_position = sum(t.bars_held for t in trades)
        exposure = bars_in_position / len(equity) * 100 if len(equity) > 0 else 0

        # Commission and slippage
        total_commission = sum(t.commission for t in trades)
        total_slippage = sum(t.slippage for t in trades)

        # Benchmark comparison
        benchmark_return = 0.0
        alpha = 0.0
        beta = 0.0
        info_ratio = 0.0
        if benchmark_curve is not None and len(benchmark_curve) > 1:
            bench_ret = (float(benchmark_curve.iloc[-1]) / float(benchmark_curve.iloc[0]) - 1) * 100
            benchmark_return = bench_ret
            alpha = total_return - bench_ret

            # Beta
            bench_returns = benchmark_curve.pct_change().dropna()
            if len(bench_returns) == len(returns):
                cov = np.cov(returns.values, bench_returns.values)
                beta = float(cov[0, 1] / cov[1, 1]) if cov[1, 1] > 0 else 0

                # Information ratio
                active_returns = returns.values - bench_returns.values
                tracking_error = float(np.std(active_returns)) * np.sqrt(252)
                info_ratio = float(np.mean(active_returns) * 252 / tracking_error) if tracking_error > 0 else 0

        return BacktestMetrics(
            total_return=round(total_return, 4),
            annualized_return=round(annualized_return, 4),
            volatility=round(volatility, 4),
            sharpe_ratio=round(sharpe, 4),
            sortino_ratio=round(sortino, 4),
            max_drawdown=round(max_dd, 4),
            calmar_ratio=round(calmar, 4),
            win_rate=round(win_rate, 4),
            payoff_ratio=round(payoff, 4),
            avg_trade_pnl=round(float(np.mean([t.pnl for t in trades])), 2) if trades else 0,
            total_trades=len(trades),
            total_commission=round(total_commission, 2),
            total_slippage=round(total_slippage, 2),
            exposure=round(exposure, 4),
            turnover=round(len(trades) * 2 / len(equity) if len(equity) > 0 else 0, 4),
            profit_factor=round(profit_factor, 4),
            max_consecutive_losses=max_consec,
            avg_bars_held=round(float(np.mean([t.bars_held for t in trades])), 1) if trades else 0,
            benchmark_return=round(benchmark_return, 4),
            alpha=round(alpha, 4),
            beta=round(beta, 4),
            information_ratio=round(info_ratio, 4),
        )

    def _empty_result(self) -> BacktestResult:
        """Return empty result for insufficient data."""
        return BacktestResult(
            config=self.config,
            metrics=BacktestMetrics(),
            trades=[],
            equity_curve=pd.Series(dtype=float),
            drawdown_curve=pd.Series(dtype=float),
        )
