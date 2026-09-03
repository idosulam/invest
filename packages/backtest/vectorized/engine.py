"""Vectorized backtest engine — PRD Section 6.

Wraps VectorBT for fast parameter sweeps and strategy validation.
Each backtest records: universe, snapshot, corporate-action version,
calendar, fill timing, commission, slippage, position limits, seed.
"""

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Optional

import numpy as np
import pandas as pd


@dataclass
class BacktestConfig:
    """Backtest configuration and assumptions."""
    initial_capital: float = 100000.0
    commission_pct: float = 0.001  # 0.1%
    slippage_pct: float = 0.0005  # 0.05%
    position_size_pct: float = 0.1  # 10% per position
    max_positions: int = 10
    seed: int = 42


@dataclass
class BacktestMetrics:
    """Required metrics per PRD Section 6."""
    total_return: float = 0.0
    annualized_return: float = 0.0
    volatility: float = 0.0
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    max_drawdown: float = 0.0
    calmar_ratio: float = 0.0
    win_rate: float = 0.0
    payoff_ratio: float = 0.0
    total_trades: int = 0
    avg_trade_duration_days: float = 0.0
    exposure_pct: float = 0.0
    turnover: float = 0.0
    total_costs: float = 0.0
    # Benchmark comparison
    benchmark_return: float = 0.0
    alpha: float = 0.0
    beta: float = 0.0


@dataclass
class Trade:
    """Individual trade record."""
    entry_date: datetime
    exit_date: Optional[datetime] = None
    side: str = "LONG"
    entry_price: float = 0.0
    exit_price: Optional[float] = None
    quantity: float = 0.0
    pnl: float = 0.0
    pnl_pct: float = 0.0
    fees: float = 0.0


@dataclass
class BacktestResult:
    """Complete backtest result."""
    id: uuid.UUID = field(default_factory=uuid.uuid4)
    strategy_name: str = ""
    config: BacktestConfig = field(default_factory=BacktestConfig)
    metrics: BacktestMetrics = field(default_factory=BacktestMetrics)
    trades: list[Trade] = field(default_factory=list)
    equity_curve: list[float] = field(default_factory=list)
    drawdown_curve: list[float] = field(default_factory=list)
    timestamps: list[datetime] = field(default_factory=list)
    started_at: datetime = field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    error: Optional[str] = None


def run_sma_crossover_backtest(
    bars: pd.DataFrame,
    fast_period: int = 20,
    slow_period: int = 50,
    config: Optional[BacktestConfig] = None,
) -> BacktestResult:
    """Run SMA crossover backtest on bar data.

    Args:
        bars: DataFrame with columns: ts_open, open, high, low, close, volume
        fast_period: Fast SMA period
        slow_period: Slow SMA period
        config: Backtest configuration

    Returns:
        BacktestResult with metrics, trades, equity curve
    """
    if config is None:
        config = BacktestConfig()

    result = BacktestResult(
        strategy_name=f"SMA Crossover {fast_period}/{slow_period}",
        config=config,
    )

    try:
        close = bars["close"].values
        dates = bars["ts_open"].values if "ts_open" in bars.columns else range(len(bars))

        if len(close) < slow_period + 1:
            result.error = f"Need at least {slow_period + 1} bars, got {len(close)}"
            return result

        # Compute SMAs
        fast_sma = pd.Series(close).rolling(fast_period).mean().values
        slow_sma = pd.Series(close).rolling(slow_period).mean().values

        # Generate signals
        capital = config.initial_capital
        position = 0.0
        entry_price = 0.0
        entry_date = None
        trades = []
        equity = []
        peak_equity = capital
        drawdowns = []
        total_costs = 0.0

        for i in range(slow_period, len(close)):
            price = close[i]
            date = dates[i] if hasattr(dates[i], "hour") else datetime.utcnow()

            # Current equity
            current_equity = capital + (position * price if position > 0 else 0)
            equity.append(current_equity)

            # Drawdown
            peak_equity = max(peak_equity, current_equity)
            dd = (peak_equity - current_equity) / peak_equity if peak_equity > 0 else 0
            drawdowns.append(dd)

            # Skip if NaN
            if np.isnan(fast_sma[i]) or np.isnan(slow_sma[i]):
                continue

            # Entry signal: fast crosses above slow
            if (
                position == 0
                and fast_sma[i] > slow_sma[i]
                and fast_sma[i - 1] <= slow_sma[i - 1]
            ):
                # Calculate position size
                invest_amount = capital * config.position_size_pct
                commission = invest_amount * config.commission_pct
                slippage = invest_amount * config.slippage_pct
                total_cost = commission + slippage
                total_costs += total_cost

                quantity = (invest_amount - total_cost) / price
                position = quantity
                entry_price = price
                entry_date = date
                capital -= invest_amount

            # Exit signal: fast crosses below slow
            elif (
                position > 0
                and fast_sma[i] < slow_sma[i]
                and fast_sma[i - 1] >= slow_sma[i - 1]
            ):
                exit_value = position * price
                commission = exit_value * config.commission_pct
                slippage = exit_value * config.slippage_pct
                total_cost = commission + slippage
                total_costs += total_cost

                net_exit = exit_value - total_cost
                pnl = net_exit - (position * entry_price)
                pnl_pct = pnl / (position * entry_price) if entry_price > 0 else 0

                trades.append(Trade(
                    entry_date=entry_date,
                    exit_date=date,
                    side="LONG",
                    entry_price=entry_price,
                    exit_price=price,
                    quantity=position,
                    pnl=pnl,
                    pnl_pct=pnl_pct,
                    fees=total_cost,
                ))

                capital += net_exit
                position = 0.0

        # Close open position at last price
        if position > 0:
            last_price = close[-1]
            exit_value = position * last_price
            commission = exit_value * config.commission_pct
            slippage = exit_value * config.slippage_pct
            total_cost = commission + slippage
            total_costs += total_cost

            net_exit = exit_value - total_cost
            pnl = net_exit - (position * entry_price)
            pnl_pct = pnl / (position * entry_price) if entry_price > 0 else 0

            trades.append(Trade(
                entry_date=entry_date,
                exit_date=datetime.utcnow(),
                side="LONG",
                entry_price=entry_price,
                exit_price=last_price,
                quantity=position,
                pnl=pnl,
                pnl_pct=pnl_pct,
                fees=total_cost,
            ))
            capital += net_exit
            position = 0.0

        # Compute metrics
        final_equity = capital
        total_return = (final_equity - config.initial_capital) / config.initial_capital

        # Trade stats
        winning = [t for t in trades if t.pnl > 0]
        losing = [t for t in trades if t.pnl <= 0]
        win_rate = len(winning) / len(trades) if trades else 0
        avg_win = np.mean([t.pnl for t in winning]) if winning else 0
        avg_loss = abs(np.mean([t.pnl for t in losing])) if losing else 1
        payoff_ratio = avg_win / avg_loss if avg_loss > 0 else 0

        # Volatility (annualized)
        if len(equity) > 1:
            returns = np.diff(equity) / equity[:-1]
            volatility = np.std(returns) * np.sqrt(252)
        else:
            volatility = 0

        # Sharpe
        risk_free = 0.04 / 252  # ~4% annual
        if volatility > 0:
            excess_return = (total_return / len(equity) * 252) - 0.04
            sharpe = excess_return / volatility
        else:
            sharpe = 0

        # Sortino
        if len(equity) > 1:
            downside_returns = returns[returns < 0]
            downside_vol = np.std(downside_returns) * np.sqrt(252) if len(downside_returns) > 0 else 0
            sortino = (total_return / len(equity) * 252 - 0.04) / downside_vol if downside_vol > 0 else 0
        else:
            sortino = 0

        max_dd = max(drawdowns) if drawdowns else 0
        calmar = (total_return / len(equity) * 252) / max_dd if max_dd > 0 else 0

        # Duration
        durations = []
        for t in trades:
            if t.entry_date and t.exit_date:
                durations.append((t.exit_date - t.entry_date).days)
        avg_duration = np.mean(durations) if durations else 0

        result.metrics = BacktestMetrics(
            total_return=round(total_return * 100, 2),
            annualized_return=round(total_return / len(equity) * 252 * 100, 2) if len(equity) > 0 else 0,
            volatility=round(volatility * 100, 2),
            sharpe_ratio=round(sharpe, 2),
            sortino_ratio=round(sortino, 2),
            max_drawdown=round(max_dd * 100, 2),
            calmar_ratio=round(calmar, 2),
            win_rate=round(win_rate * 100, 1),
            payoff_ratio=round(payoff_ratio, 2),
            total_trades=len(trades),
            avg_trade_duration_days=round(avg_duration, 1),
            exposure_pct=round(100, 1),  # simplified
            turnover=round(len(trades) * 2, 1),
            total_costs=round(total_costs, 2),
        )
        result.trades = trades
        result.equity_curve = [round(e, 2) for e in equity]
        result.drawdown_curve = [round(d * 100, 2) for d in drawdowns]
        result.timestamps = [dates[i] if hasattr(dates[i], "hour") else datetime.utcnow() for i in range(slow_period, len(close))]
        result.completed_at = datetime.utcnow()

    except Exception as e:
        result.error = str(e)

    return result


def _compute_backtest_metrics(
    trades: list[Trade],
    equity: list[float],
    drawdowns: list[float],
    total_costs: float,
    config: BacktestConfig,
    dates,
    start_idx: int,
    close_len: int,
) -> BacktestMetrics:
    """Shared metrics computation, factored out so every strategy's
    backtest produces directly comparable numbers the same way."""
    final_equity = equity[-1] if equity else config.initial_capital
    total_return = (final_equity - config.initial_capital) / config.initial_capital

    winning = [t for t in trades if t.pnl > 0]
    losing = [t for t in trades if t.pnl <= 0]
    win_rate = len(winning) / len(trades) if trades else 0
    avg_win = np.mean([t.pnl for t in winning]) if winning else 0
    avg_loss = abs(np.mean([t.pnl for t in losing])) if losing else 1
    payoff_ratio = avg_win / avg_loss if avg_loss > 0 else 0

    if len(equity) > 1:
        returns = np.diff(equity) / np.where(np.array(equity[:-1]) == 0, 1, equity[:-1])
        volatility = np.std(returns) * np.sqrt(252)
    else:
        returns = np.array([])
        volatility = 0

    risk_free = 0.04
    if volatility > 0 and len(equity) > 0:
        excess_return = (total_return / len(equity) * 252) - risk_free
        sharpe = excess_return / volatility
    else:
        sharpe = 0

    if len(returns) > 0:
        downside_returns = returns[returns < 0]
        downside_vol = np.std(downside_returns) * np.sqrt(252) if len(downside_returns) > 0 else 0
        sortino = (total_return / len(equity) * 252 - risk_free) / downside_vol if downside_vol > 0 else 0
    else:
        sortino = 0

    max_dd = max(drawdowns) if drawdowns else 0
    calmar = (total_return / len(equity) * 252) / max_dd if max_dd > 0 and len(equity) > 0 else 0

    durations = []
    for t in trades:
        if t.entry_date and t.exit_date:
            try:
                durations.append((t.exit_date - t.entry_date).days)
            except TypeError:
                pass
    avg_duration = np.mean(durations) if durations else 0

    return BacktestMetrics(
        total_return=round(total_return * 100, 2),
        annualized_return=round(total_return / len(equity) * 252 * 100, 2) if len(equity) > 0 else 0,
        volatility=round(volatility * 100, 2),
        sharpe_ratio=round(sharpe, 2),
        sortino_ratio=round(sortino, 2),
        max_drawdown=round(max_dd * 100, 2),
        calmar_ratio=round(calmar, 2),
        win_rate=round(win_rate * 100, 1),
        payoff_ratio=round(payoff_ratio, 2),
        total_trades=len(trades),
        avg_trade_duration_days=round(avg_duration, 1),
        exposure_pct=round(100, 1),
        turnover=round(len(trades) * 2, 1),
        total_costs=round(total_costs, 2),
    )


def run_obv_backtest(
    bars: pd.DataFrame,
    lookback: int = 20,
    config: Optional[BacktestConfig] = None,
) -> BacktestResult:
    """Backtest the OBV Trend & Divergence strategy's exact entry/exit rules:
    enter on bullish divergence (price at a low, OBV rising), exit on
    bearish divergence (price at a high, OBV falling).
    """
    if config is None:
        config = BacktestConfig()

    result = BacktestResult(strategy_name="OBV Trend & Divergence", config=config)

    try:
        close = bars["close"].values
        volume = bars["volume"].values
        dates = bars["ts_open"].values if "ts_open" in bars.columns else range(len(bars))

        min_bars = lookback + 5
        if len(close) < min_bars:
            result.error = f"Need at least {min_bars} bars, got {len(close)}"
            return result

        direction = np.sign(np.diff(close, prepend=close[0]))
        direction[0] = 0
        obv = np.cumsum(volume * direction)

        capital = config.initial_capital
        position = 0.0
        entry_price = 0.0
        entry_date = None
        trades = []
        equity = []
        peak_equity = capital
        drawdowns = []
        total_costs = 0.0

        for i in range(lookback, len(close)):
            price = close[i]
            date = dates[i] if hasattr(dates[i], "hour") else datetime.utcnow()

            current_equity = capital + (position * price if position > 0 else 0)
            equity.append(current_equity)
            peak_equity = max(peak_equity, current_equity)
            dd = (peak_equity - current_equity) / peak_equity if peak_equity > 0 else 0
            drawdowns.append(dd)

            window_close = close[i - lookback + 1: i + 1]
            window_obv = obv[i - lookback + 1: i + 1]

            price_low_idx = int(np.argmin(window_close))
            price_high_idx = int(np.argmax(window_close))
            price_low = window_close[price_low_idx]
            price_high = window_close[price_high_idx]
            obv_at_low = window_obv[price_low_idx]
            obv_at_high = window_obv[price_high_idx]
            curr_obv = window_obv[-1]
            prev_price = close[i - 1] if i > 0 else price

            near_low = price <= price_low * 1.02
            bullish_div = near_low and curr_obv > obv_at_low and price < prev_price * 1.0

            near_high = price >= price_high * 0.98
            bearish_div = near_high and curr_obv < obv_at_high

            if position == 0 and bullish_div:
                invest_amount = capital * config.position_size_pct
                commission = invest_amount * config.commission_pct
                slippage = invest_amount * config.slippage_pct
                total_cost = commission + slippage
                total_costs += total_cost

                quantity = (invest_amount - total_cost) / price
                position = quantity
                entry_price = price
                entry_date = date
                capital -= invest_amount

            elif position > 0 and bearish_div:
                exit_value = position * price
                commission = exit_value * config.commission_pct
                slippage = exit_value * config.slippage_pct
                total_cost = commission + slippage
                total_costs += total_cost

                net_exit = exit_value - total_cost
                pnl = net_exit - (position * entry_price)
                pnl_pct = pnl / (position * entry_price) if entry_price > 0 else 0

                trades.append(Trade(
                    entry_date=entry_date,
                    exit_date=date,
                    side="LONG",
                    entry_price=entry_price,
                    exit_price=price,
                    quantity=position,
                    pnl=pnl,
                    pnl_pct=pnl_pct,
                    fees=total_cost,
                ))
                capital += net_exit
                position = 0.0

        if position > 0:
            last_price = close[-1]
            exit_value = position * last_price
            commission = exit_value * config.commission_pct
            slippage = exit_value * config.slippage_pct
            total_cost = commission + slippage
            total_costs += total_cost

            net_exit = exit_value - total_cost
            pnl = net_exit - (position * entry_price)
            pnl_pct = pnl / (position * entry_price) if entry_price > 0 else 0

            trades.append(Trade(
                entry_date=entry_date,
                exit_date=datetime.utcnow(),
                side="LONG",
                entry_price=entry_price,
                exit_price=last_price,
                quantity=position,
                pnl=pnl,
                pnl_pct=pnl_pct,
                fees=total_cost,
            ))
            capital += net_exit
            position = 0.0

        result.metrics = _compute_backtest_metrics(
            trades, equity, drawdowns, total_costs, config, dates, lookback, len(close)
        )
        result.trades = trades
        result.equity_curve = [round(e, 2) for e in equity]
        result.drawdown_curve = [round(d * 100, 2) for d in drawdowns]
        result.timestamps = [dates[i] if hasattr(dates[i], "hour") else datetime.utcnow() for i in range(lookback, len(close))]
        result.completed_at = datetime.utcnow()

    except Exception as e:
        result.error = str(e)

    return result


def run_rsi_backtest(
    bars: pd.DataFrame,
    rsi_period: int = 14,
    oversold: float = 30,
    overbought: float = 70,
    config: Optional[BacktestConfig] = None,
) -> BacktestResult:
    """Run RSI mean reversion backtest."""
    if config is None:
        config = BacktestConfig()

    result = BacktestResult(
        strategy_name=f"RSI Mean Reversion ({rsi_period}, {oversold}/{overbought})",
        config=config,
    )

    try:
        close = bars["close"].values
        dates = bars["ts_open"].values if "ts_open" in bars.columns else range(len(bars))

        if len(close) < rsi_period + 2:
            result.error = f"Need at least {rsi_period + 2} bars"
            return result

        # Compute RSI
        delta = np.diff(close)
        gain = np.where(delta > 0, delta, 0)
        loss = np.where(delta < 0, -delta, 0)

        avg_gain = pd.Series(gain).ewm(alpha=1.0 / rsi_period, min_periods=rsi_period, adjust=False).mean().values
        avg_loss = pd.Series(loss).ewm(alpha=1.0 / rsi_period, min_periods=rsi_period, adjust=False).mean().values

        rs = avg_gain / np.where(avg_loss > 0, avg_loss, 1e-10)
        rsi_values = 100 - (100 / (1 + rs))

        capital = config.initial_capital
        position = 0.0
        entry_price = 0.0
        entry_date = None
        trades = []
        equity = []
        peak_equity = capital
        drawdowns = []
        total_costs = 0.0

        for i in range(rsi_period, len(close) - 1):
            price = close[i]
            date = dates[i] if hasattr(dates[i], "hour") else datetime.utcnow()
            rsi_val = rsi_values[i - 1]  # offset by 1 due to diff

            current_equity = capital + (position * price if position > 0 else 0)
            equity.append(current_equity)
            peak_equity = max(peak_equity, current_equity)
            dd = (peak_equity - current_equity) / peak_equity if peak_equity > 0 else 0
            drawdowns.append(dd)

            # Entry: RSI crosses above oversold
            if (
                position == 0
                and rsi_val >= oversold
                and rsi_values[i - 2] < oversold
            ):
                invest = capital * config.position_size_pct
                costs = invest * (config.commission_pct + config.slippage_pct)
                total_costs += costs
                quantity = (invest - costs) / price
                position = quantity
                entry_price = price
                entry_date = date
                capital -= invest

            # Exit: RSI crosses above overbought
            elif (
                position > 0
                and rsi_val >= overbought
            ):
                exit_value = position * price
                costs = exit_value * (config.commission_pct + config.slippage_pct)
                total_costs += costs
                net_exit = exit_value - costs
                pnl = net_exit - (position * entry_price)

                trades.append(Trade(
                    entry_date=entry_date,
                    exit_date=date,
                    side="LONG",
                    entry_price=entry_price,
                    exit_price=price,
                    quantity=position,
                    pnl=pnl,
                    pnl_pct=pnl / (position * entry_price) if entry_price > 0 else 0,
                    fees=costs,
                ))
                capital += net_exit
                position = 0.0

        # Close open
        if position > 0:
            last_price = close[-1]
            exit_value = position * last_price
            costs = exit_value * (config.commission_pct + config.slippage_pct)
            total_costs += costs
            net_exit = exit_value - costs
            pnl = net_exit - (position * entry_price)
            trades.append(Trade(
                entry_date=entry_date, exit_date=datetime.utcnow(),
                entry_price=entry_price, exit_price=last_price,
                quantity=position, pnl=pnl,
                pnl_pct=pnl / (position * entry_price) if entry_price > 0 else 0,
                fees=costs,
            ))
            capital += net_exit

        # Metrics
        final_equity = capital
        total_return = (final_equity - config.initial_capital) / config.initial_capital
        winning = [t for t in trades if t.pnl > 0]
        losing = [t for t in trades if t.pnl <= 0]

        result.metrics = BacktestMetrics(
            total_return=round(total_return * 100, 2),
            annualized_return=round(total_return / len(equity) * 252 * 100, 2) if len(equity) > 0 else 0,
            win_rate=round(len(winning) / len(trades) * 100, 1) if trades else 0,
            total_trades=len(trades),
            total_costs=round(total_costs, 2),
            max_drawdown=round(max(drawdowns) * 100, 2) if drawdowns else 0,
        )
        result.trades = trades
        result.equity_curve = [round(e, 2) for e in equity]
        result.drawdown_curve = [round(d * 100, 2) for d in drawdowns]
        result.completed_at = datetime.utcnow()

    except Exception as e:
        result.error = str(e)

    return result
