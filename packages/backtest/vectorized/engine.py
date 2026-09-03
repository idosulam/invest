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


def _to_python_datetime(val) -> datetime:
    """Convert numpy datetime64, pandas Timestamp, or Python datetime
    to a plain Python datetime.  Falls back to utcnow() only if the
    value is completely unrecognisable."""
    if isinstance(val, datetime):
        return val
    if hasattr(val, "to_pydatetime"):          # pandas Timestamp
        return val.to_py_datetime() if hasattr(val, "to_py_datetime") else val.to_pydatetime()
    if isinstance(val, np.datetime64):           # numpy datetime64
        return pd.Timestamp(val).to_pydatetime()
    # Last resort — shouldn't happen with real bar data
    return datetime.utcnow()


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
    data_caveat: Optional[str] = None


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
            date = _to_python_datetime(dates[i])

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
        avg_loss = abs(np.mean([t.pnl for t in losing])) if losing else 0
        if avg_loss > 0:
            payoff_ratio = avg_win / avg_loss
        elif len(winning) > 0:
            payoff_ratio = float("inf")  # all wins, no losses
        else:
            payoff_ratio = 0.0

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
        result.timestamps = [_to_python_datetime(dates[i]) for i in range(slow_period, len(close))]
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
    avg_loss = abs(np.mean([t.pnl for t in losing])) if losing else 0
    if avg_loss > 0:
        payoff_ratio = avg_win / avg_loss
    elif len(winning) > 0:
        payoff_ratio = float("inf")  # all wins, no losses
    else:
        payoff_ratio = 0.0

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
            date = _to_python_datetime(dates[i])

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
        result.timestamps = [_to_python_datetime(dates[i]) for i in range(lookback, len(close))]
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
            date = _to_python_datetime(dates[i])
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

        # Metrics — use shared computation for consistency
        result.metrics = _compute_backtest_metrics(
            trades, equity, drawdowns, total_costs, config, dates, rsi_period, len(close)
        )
        result.trades = trades
        result.equity_curve = [round(e, 2) for e in equity]
        result.drawdown_curve = [round(d * 100, 2) for d in drawdowns]
        result.timestamps = [_to_python_datetime(dates[i]) for i in range(rsi_period, rsi_period + len(equity))]
        result.completed_at = datetime.utcnow()

    except Exception as e:
        result.error = str(e)

    return result


# ── Intraday strategy backtests (daily-bar approximation) ────────
# These strategies are designed for intraday bars (5m/1m).  Until
# intraday bar ingestion exists, we backtest them on daily bars with
# an explicit caveat so results are stored but flagged as not
# representative of their real intraday behaviour.

_INTRADAY_DATA_CAVEAT = (
    "Backtested on daily bars — this strategy is designed for intraday "
    "(5-minute) data.  Results are indicative only and NOT representative "
    "of real intraday performance.  Re-run once intraday bar ingestion "
    "is available."
)


def run_opening_range_breakout_backtest(
    bars: pd.DataFrame,
    or_bars: int = 2,
    config: Optional[BacktestConfig] = None,
) -> BacktestResult:
    """Backtest Opening Range Breakout on daily bars.

    Approximates the intraday ORB strategy: uses the first *or_bars*
    daily bars to define the opening range, then trades breakouts.
    """
    if config is None:
        config = BacktestConfig()

    result = BacktestResult(
        strategy_name="Opening Range Breakout",
        config=config,
    )
    result.data_caveat = _INTRADAY_DATA_CAVEAT

    try:
        close = bars["close"].values
        high = bars["high"].values
        low = bars["low"].values
        volume = bars["volume"].values
        dates = bars["ts_open"].values if "ts_open" in bars.columns else range(len(bars))

        if len(close) < or_bars + 10:
            result.error = f"Need at least {or_bars + 10} bars, got {len(close)}"
            return result

        capital = config.initial_capital
        position = 0.0
        entry_price = 0.0
        entry_date = None
        trades: list[Trade] = []
        equity: list[float] = []
        peak_equity = capital
        drawdowns: list[float] = []
        total_costs = 0.0

        # Rolling opening range: use a sliding window of the first
        # *or_bars* bars in each "session" (approximated as every
        # *or_bars* bars on daily data).
        session_len = or_bars * 5  # ~5 trading days per "session"

        for i in range(or_bars, len(close)):
            price = close[i]
            date = _to_python_datetime(dates[i])

            current_equity = capital + (position * price if position > 0 else 0)
            equity.append(current_equity)
            peak_equity = max(peak_equity, current_equity)
            dd = (peak_equity - current_equity) / peak_equity if peak_equity > 0 else 0
            drawdowns.append(dd)

            # Session boundary: reset opening range
            session_start = (i // session_len) * session_len
            or_end = min(session_start + or_bars, len(close))
            if i < or_end:
                continue

            or_high = float(high[session_start:or_end].max())
            or_low = float(low[session_start:or_end].min())
            or_range = or_high - or_low
            if or_range <= 0:
                continue

            avg_vol = float(volume[session_start:or_end].mean()) if or_end > session_start else 0
            vol_surge = float(volume[i]) > avg_vol * 1.5 if avg_vol > 0 else False

            # Entry: breakout above OR high with volume
            if position == 0 and price > or_high and vol_surge:
                invest = capital * config.position_size_pct
                costs = invest * (config.commission_pct + config.slippage_pct)
                total_costs += costs
                quantity = (invest - costs) / price
                position = quantity
                entry_price = price
                entry_date = date
                capital -= invest

            # Exit: break below OR low
            elif position > 0 and price < or_low:
                exit_value = position * price
                costs = exit_value * (config.commission_pct + config.slippage_pct)
                total_costs += costs
                net_exit = exit_value - costs
                pnl = net_exit - (position * entry_price)
                trades.append(Trade(
                    entry_date=entry_date, exit_date=date, side="LONG",
                    entry_price=entry_price, exit_price=price,
                    quantity=position, pnl=pnl,
                    pnl_pct=pnl / (position * entry_price) if entry_price > 0 else 0,
                    fees=costs,
                ))
                capital += net_exit
                position = 0.0

        # Close open position
        if position > 0:
            last_price = close[-1]
            exit_value = position * last_price
            costs = exit_value * (config.commission_pct + config.slippage_pct)
            total_costs += costs
            net_exit = exit_value - costs
            pnl = net_exit - (position * entry_price)
            trades.append(Trade(
                entry_date=entry_date, exit_date=datetime.utcnow(), side="LONG",
                entry_price=entry_price, exit_price=last_price,
                quantity=position, pnl=pnl,
                pnl_pct=pnl / (position * entry_price) if entry_price > 0 else 0,
                fees=costs,
            ))
            capital += net_exit

        result.metrics = _compute_backtest_metrics(
            trades, equity, drawdowns, total_costs, config, dates, or_bars, len(close)
        )
        result.trades = trades
        result.equity_curve = [round(e, 2) for e in equity]
        result.drawdown_curve = [round(d * 100, 2) for d in drawdowns]
        result.timestamps = [_to_python_datetime(dates[i]) for i in range(or_bars, or_bars + len(equity))]
        result.completed_at = datetime.utcnow()

    except Exception as e:
        result.error = str(e)

    return result


def run_vwap_reclaim_backtest(
    bars: pd.DataFrame,
    vwap_period: int = 20,
    config: Optional[BacktestConfig] = None,
) -> BacktestResult:
    """Backtest VWAP Reclaim/Rejection on daily bars.

    Uses a rolling VWAP approximation (typical price × volume / rolling
    volume sum) and trades crossovers.
    """
    if config is None:
        config = BacktestConfig()

    result = BacktestResult(
        strategy_name="VWAP Reclaim/Rejection",
        config=config,
    )
    result.data_caveat = _INTRADAY_DATA_CAVEAT

    try:
        close = bars["close"].values
        high = bars["high"].values
        low = bars["low"].values
        volume = bars["volume"].values
        dates = bars["ts_open"].values if "ts_open" in bars.columns else range(len(bars))

        if len(close) < vwap_period + 5:
            result.error = f"Need at least {vwap_period + 5} bars"
            return result

        # Rolling VWAP approximation
        typical_price = (high + low + close) / 3.0
        tp_vol = typical_price * volume
        rolling_tp_vol = pd.Series(tp_vol).rolling(vwap_period).sum().values
        rolling_vol = pd.Series(volume).rolling(vwap_period).sum().values
        vwap = np.where(rolling_vol > 0, rolling_tp_vol / rolling_vol, close)

        # RSI for confirmation
        delta = np.diff(close)
        gain = np.where(delta > 0, delta, 0)
        loss = np.where(delta < 0, -delta, 0)
        avg_gain = pd.Series(gain).ewm(alpha=1.0 / 14, min_periods=14, adjust=False).mean().values
        avg_loss = pd.Series(loss).ewm(alpha=1.0 / 14, min_periods=14, adjust=False).mean().values
        rs = avg_gain / np.where(avg_loss > 0, avg_loss, 1e-10)
        rsi = 100 - (100 / (1 + rs))

        capital = config.initial_capital
        position = 0.0
        entry_price = 0.0
        entry_date = None
        trades: list[Trade] = []
        equity: list[float] = []
        peak_equity = capital
        drawdowns: list[float] = []
        total_costs = 0.0

        start = vwap_period + 1
        for i in range(start, len(close)):
            price = close[i]
            date = _to_python_datetime(dates[i])

            current_equity = capital + (position * price if position > 0 else 0)
            equity.append(current_equity)
            peak_equity = max(peak_equity, current_equity)
            dd = (peak_equity - current_equity) / peak_equity if peak_equity > 0 else 0
            drawdowns.append(dd)

            curr_vwap = vwap[i]
            prev_vwap = vwap[i - 1]
            vol_ratio = float(volume[i]) / float(volume[i - vwap_period:i].mean()) if i >= vwap_period else 1.0
            rsi_val = rsi[i - 2] if i >= 2 else 50  # offset for diff

            crossed_above = close[i - 1] <= prev_vwap and price > curr_vwap
            crossed_below = close[i - 1] >= prev_vwap and price < curr_vwap

            # Entry: VWAP reclaim with volume
            if position == 0 and crossed_above and vol_ratio > 1.2:
                invest = capital * config.position_size_pct
                costs = invest * (config.commission_pct + config.slippage_pct)
                total_costs += costs
                quantity = (invest - costs) / price
                position = quantity
                entry_price = price
                entry_date = date
                capital -= invest

            # Exit: VWAP rejection with volume
            elif position > 0 and crossed_below and vol_ratio > 1.2:
                exit_value = position * price
                costs = exit_value * (config.commission_pct + config.slippage_pct)
                total_costs += costs
                net_exit = exit_value - costs
                pnl = net_exit - (position * entry_price)
                trades.append(Trade(
                    entry_date=entry_date, exit_date=date, side="LONG",
                    entry_price=entry_price, exit_price=price,
                    quantity=position, pnl=pnl,
                    pnl_pct=pnl / (position * entry_price) if entry_price > 0 else 0,
                    fees=costs,
                ))
                capital += net_exit
                position = 0.0

            # Also exit if RSI overbought
            elif position > 0 and rsi_val > 70:
                exit_value = position * price
                costs = exit_value * (config.commission_pct + config.slippage_pct)
                total_costs += costs
                net_exit = exit_value - costs
                pnl = net_exit - (position * entry_price)
                trades.append(Trade(
                    entry_date=entry_date, exit_date=date, side="LONG",
                    entry_price=entry_price, exit_price=price,
                    quantity=position, pnl=pnl,
                    pnl_pct=pnl / (position * entry_price) if entry_price > 0 else 0,
                    fees=costs,
                ))
                capital += net_exit
                position = 0.0

        if position > 0:
            last_price = close[-1]
            exit_value = position * last_price
            costs = exit_value * (config.commission_pct + config.slippage_pct)
            total_costs += costs
            net_exit = exit_value - costs
            pnl = net_exit - (position * entry_price)
            trades.append(Trade(
                entry_date=entry_date, exit_date=datetime.utcnow(), side="LONG",
                entry_price=entry_price, exit_price=last_price,
                quantity=position, pnl=pnl,
                pnl_pct=pnl / (position * entry_price) if entry_price > 0 else 0,
                fees=costs,
            ))
            capital += net_exit

        result.metrics = _compute_backtest_metrics(
            trades, equity, drawdowns, total_costs, config, dates, start, len(close)
        )
        result.trades = trades
        result.equity_curve = [round(e, 2) for e in equity]
        result.drawdown_curve = [round(d * 100, 2) for d in drawdowns]
        result.timestamps = [_to_python_datetime(dates[i]) for i in range(start, start + len(equity))]
        result.completed_at = datetime.utcnow()

    except Exception as e:
        result.error = str(e)

    return result


def run_intraday_momentum_backtest(
    bars: pd.DataFrame,
    rsi_period: int = 14,
    fast_ema: int = 12,
    slow_ema: int = 26,
    config: Optional[BacktestConfig] = None,
) -> BacktestResult:
    """Backtest Intraday Momentum on daily bars.

    Uses ROC, RSI, and EMA crossover — same logic as the live strategy
    but on daily bars.
    """
    if config is None:
        config = BacktestConfig()

    result = BacktestResult(
        strategy_name="Intraday Momentum",
        config=config,
    )
    result.data_caveat = _INTRADAY_DATA_CAVEAT

    try:
        close = bars["close"].values
        volume = bars["volume"].values
        dates = bars["ts_open"].values if "ts_open" in bars.columns else range(len(bars))

        min_bars = max(slow_ema, rsi_period) + 5
        if len(close) < min_bars:
            result.error = f"Need at least {min_bars} bars"
            return result

        # EMAs
        ema_fast = pd.Series(close).ewm(span=fast_ema, adjust=False).mean().values
        ema_slow = pd.Series(close).ewm(span=slow_ema, adjust=False).mean().values

        # RSI
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
        trades: list[Trade] = []
        equity: list[float] = []
        peak_equity = capital
        drawdowns: list[float] = []
        total_costs = 0.0

        start = slow_ema + 1
        for i in range(start, len(close)):
            price = close[i]
            date = _to_python_datetime(dates[i])

            current_equity = capital + (position * price if position > 0 else 0)
            equity.append(current_equity)
            peak_equity = max(peak_equity, current_equity)
            dd = (peak_equity - current_equity) / peak_equity if peak_equity > 0 else 0
            drawdowns.append(dd)

            # ROC (5-bar rate of change)
            roc_5 = (price - close[i - 5]) / close[i - 5] * 100 if i >= 5 else 0
            rsi_val = rsi_values[i - 1] if i >= 1 else 50
            vol_ratio = float(volume[i]) / float(volume[max(0, i - 20):i].mean()) if i >= 5 else 1.0

            ema_bullish = ema_fast[i] > ema_slow[i]
            ema_cross_up = ema_fast[i - 1] <= ema_slow[i - 1] and ema_fast[i] > ema_slow[i]

            # Entry: strong momentum
            if (
                position == 0
                and roc_5 > 0.5
                and rsi_val > 55 and rsi_val < 80
                and vol_ratio > 1.3
                and ema_bullish
            ):
                invest = capital * config.position_size_pct
                costs = invest * (config.commission_pct + config.slippage_pct)
                total_costs += costs
                quantity = (invest - costs) / price
                position = quantity
                entry_price = price
                entry_date = date
                capital -= invest

            # Entry: EMA crossover with volume
            elif (
                position == 0
                and ema_cross_up
                and vol_ratio > 1.2
            ):
                invest = capital * config.position_size_pct
                costs = invest * (config.commission_pct + config.slippage_pct)
                total_costs += costs
                quantity = (invest - costs) / price
                position = quantity
                entry_price = price
                entry_date = date
                capital -= invest

            # Exit: momentum fading
            elif position > 0 and (roc_5 < -0.3 and rsi_val < 45):
                exit_value = position * price
                costs = exit_value * (config.commission_pct + config.slippage_pct)
                total_costs += costs
                net_exit = exit_value - costs
                pnl = net_exit - (position * entry_price)
                trades.append(Trade(
                    entry_date=entry_date, exit_date=date, side="LONG",
                    entry_price=entry_price, exit_price=price,
                    quantity=position, pnl=pnl,
                    pnl_pct=pnl / (position * entry_price) if entry_price > 0 else 0,
                    fees=costs,
                ))
                capital += net_exit
                position = 0.0

            # Exit: RSI overbought
            elif position > 0 and rsi_val > 80:
                exit_value = position * price
                costs = exit_value * (config.commission_pct + config.slippage_pct)
                total_costs += costs
                net_exit = exit_value - costs
                pnl = net_exit - (position * entry_price)
                trades.append(Trade(
                    entry_date=entry_date, exit_date=date, side="LONG",
                    entry_price=entry_price, exit_price=price,
                    quantity=position, pnl=pnl,
                    pnl_pct=pnl / (position * entry_price) if entry_price > 0 else 0,
                    fees=costs,
                ))
                capital += net_exit
                position = 0.0

        if position > 0:
            last_price = close[-1]
            exit_value = position * last_price
            costs = exit_value * (config.commission_pct + config.slippage_pct)
            total_costs += costs
            net_exit = exit_value - costs
            pnl = net_exit - (position * entry_price)
            trades.append(Trade(
                entry_date=entry_date, exit_date=datetime.utcnow(), side="LONG",
                entry_price=entry_price, exit_price=last_price,
                quantity=position, pnl=pnl,
                pnl_pct=pnl / (position * entry_price) if entry_price > 0 else 0,
                fees=costs,
            ))
            capital += net_exit

        result.metrics = _compute_backtest_metrics(
            trades, equity, drawdowns, total_costs, config, dates, start, len(close)
        )
        result.trades = trades
        result.equity_curve = [round(e, 2) for e in equity]
        result.drawdown_curve = [round(d * 100, 2) for d in drawdowns]
        result.timestamps = [_to_python_datetime(dates[i]) for i in range(start, start + len(equity))]
        result.completed_at = datetime.utcnow()

    except Exception as e:
        result.error = str(e)

    return result


def run_volatility_expansion_backtest(
    bars: pd.DataFrame,
    bb_period: int = 20,
    bb_std: float = 2.0,
    config: Optional[BacktestConfig] = None,
) -> BacktestResult:
    """Backtest Volatility Expansion (Bollinger Band squeeze breakout) on daily bars."""
    if config is None:
        config = BacktestConfig()

    result = BacktestResult(
        strategy_name="Volatility Expansion",
        config=config,
    )
    result.data_caveat = _INTRADAY_DATA_CAVEAT

    try:
        close = bars["close"].values
        volume = bars["volume"].values
        dates = bars["ts_open"].values if "ts_open" in bars.columns else range(len(bars))

        if len(close) < bb_period + 10:
            result.error = f"Need at least {bb_period + 10} bars"
            return result

        # Bollinger Bands
        sma = pd.Series(close).rolling(bb_period).mean().values
        std = pd.Series(close).rolling(bb_period).std().values
        bb_upper = sma + bb_std * std
        bb_lower = sma - bb_std * std

        # RSI
        delta = np.diff(close)
        gain = np.where(delta > 0, delta, 0)
        loss = np.where(delta < 0, -delta, 0)
        avg_gain = pd.Series(gain).ewm(alpha=1.0 / 14, min_periods=14, adjust=False).mean().values
        avg_loss = pd.Series(loss).ewm(alpha=1.0 / 14, min_periods=14, adjust=False).mean().values
        rs = avg_gain / np.where(avg_loss > 0, avg_loss, 1e-10)
        rsi_values = 100 - (100 / (1 + rs))

        capital = config.initial_capital
        position = 0.0
        entry_price = 0.0
        entry_date = None
        trades: list[Trade] = []
        equity: list[float] = []
        peak_equity = capital
        drawdowns: list[float] = []
        total_costs = 0.0

        start = bb_period + 1
        for i in range(start, len(close)):
            price = close[i]
            date = _to_python_datetime(dates[i])

            current_equity = capital + (position * price if position > 0 else 0)
            equity.append(current_equity)
            peak_equity = max(peak_equity, current_equity)
            dd = (peak_equity - current_equity) / peak_equity if peak_equity > 0 else 0
            drawdowns.append(dd)

            if np.isnan(bb_upper[i]) or np.isnan(bb_lower[i]):
                continue

            bandwidth = (bb_upper[i] - bb_lower[i]) / price if price > 0 else 0
            prev_bandwidth = (bb_upper[i - 1] - bb_lower[i - 1]) / close[i - 1] if close[i - 1] > 0 else 0

            # Squeeze: bandwidth in bottom 20% of recent 20-bar range
            recent_bw = []
            for j in range(max(0, i - 20), i):
                if not np.isnan(bb_upper[j]) and close[j] > 0:
                    recent_bw.append((bb_upper[j] - bb_lower[j]) / close[j])
            if len(recent_bw) >= 10:
                bw_min = min(recent_bw)
                bw_max = max(recent_bw)
                bw_range = bw_max - bw_min
                squeeze_active = bandwidth < bw_min + bw_range * 0.2 if bw_range > 0 else False
            else:
                squeeze_active = False

            expanding = bandwidth > prev_bandwidth * 1.1
            pct_b = (price - bb_lower[i]) / (bb_upper[i] - bb_lower[i]) if (bb_upper[i] - bb_lower[i]) > 0 else 0.5
            vol_ratio = float(volume[i]) / float(volume[max(0, i - 20):i].mean()) if i >= 5 else 1.0
            rsi_val = rsi_values[i - 1] if i >= 1 else 50

            # Entry: squeeze breakout bullish
            if (
                position == 0
                and squeeze_active and expanding
                and pct_b > 0.8 and vol_ratio > 1.3
            ):
                invest = capital * config.position_size_pct
                costs = invest * (config.commission_pct + config.slippage_pct)
                total_costs += costs
                quantity = (invest - costs) / price
                position = quantity
                entry_price = price
                entry_date = date
                capital -= invest

            # Exit: squeeze breakdown bearish
            elif (
                position > 0
                and squeeze_active and expanding
                and pct_b < 0.2 and vol_ratio > 1.3
            ):
                exit_value = position * price
                costs = exit_value * (config.commission_pct + config.slippage_pct)
                total_costs += costs
                net_exit = exit_value - costs
                pnl = net_exit - (position * entry_price)
                trades.append(Trade(
                    entry_date=entry_date, exit_date=date, side="LONG",
                    entry_price=entry_price, exit_price=price,
                    quantity=position, pnl=pnl,
                    pnl_pct=pnl / (position * entry_price) if entry_price > 0 else 0,
                    fees=costs,
                ))
                capital += net_exit
                position = 0.0

            # Exit: overbought after expansion
            elif position > 0 and pct_b > 1.0 and rsi_val > 75:
                exit_value = position * price
                costs = exit_value * (config.commission_pct + config.slippage_pct)
                total_costs += costs
                net_exit = exit_value - costs
                pnl = net_exit - (position * entry_price)
                trades.append(Trade(
                    entry_date=entry_date, exit_date=date, side="LONG",
                    entry_price=entry_price, exit_price=price,
                    quantity=position, pnl=pnl,
                    pnl_pct=pnl / (position * entry_price) if entry_price > 0 else 0,
                    fees=costs,
                ))
                capital += net_exit
                position = 0.0

            # Exit: close below SMA(20)
            elif position > 0 and price < sma[i] and not np.isnan(sma[i]):
                exit_value = position * price
                costs = exit_value * (config.commission_pct + config.slippage_pct)
                total_costs += costs
                net_exit = exit_value - costs
                pnl = net_exit - (position * entry_price)
                trades.append(Trade(
                    entry_date=entry_date, exit_date=date, side="LONG",
                    entry_price=entry_price, exit_price=price,
                    quantity=position, pnl=pnl,
                    pnl_pct=pnl / (position * entry_price) if entry_price > 0 else 0,
                    fees=costs,
                ))
                capital += net_exit
                position = 0.0

        if position > 0:
            last_price = close[-1]
            exit_value = position * last_price
            costs = exit_value * (config.commission_pct + config.slippage_pct)
            total_costs += costs
            net_exit = exit_value - costs
            pnl = net_exit - (position * entry_price)
            trades.append(Trade(
                entry_date=entry_date, exit_date=datetime.utcnow(), side="LONG",
                entry_price=entry_price, exit_price=last_price,
                quantity=position, pnl=pnl,
                pnl_pct=pnl / (position * entry_price) if entry_price > 0 else 0,
                fees=costs,
            ))
            capital += net_exit

        result.metrics = _compute_backtest_metrics(
            trades, equity, drawdowns, total_costs, config, dates, start, len(close)
        )
        result.trades = trades
        result.equity_curve = [round(e, 2) for e in equity]
        result.drawdown_curve = [round(d * 100, 2) for d in drawdowns]
        result.timestamps = [_to_python_datetime(dates[i]) for i in range(start, start + len(equity))]
        result.completed_at = datetime.utcnow()

    except Exception as e:
        result.error = str(e)

    return result


def run_relative_strength_spy_backtest(
    bars: pd.DataFrame,
    benchmark_bars: pd.DataFrame,
    rs_lookback_short: int = 20,
    rs_lookback_long: int = 60,
    config: Optional[BacktestConfig] = None,
) -> BacktestResult:
    """Backtest Relative Strength vs SPY strategy.

    Compares rolling returns of the stock vs benchmark (SPY).
    Enters on outperformance with acceleration, exits on underperformance.
    """
    if config is None:
        config = BacktestConfig()

    result = BacktestResult(
        strategy_name="Relative Strength vs SPY",
        config=config,
    )

    try:
        close = bars["close"].values
        dates = bars["ts_open"].values if "ts_open" in bars.columns else range(len(bars))
        bench_close = benchmark_bars["close"].values

        min_bars = max(rs_lookback_long, rs_lookback_short) + 5
        if len(close) < min_bars or len(bench_close) < min_bars:
            result.error = f"Need at least {min_bars} bars for both stock and benchmark"
            return result

        # Align benchmark to stock length
        bench_close = bench_close[-len(close):]

        # SMA(20) for trend confirmation
        sma_20 = pd.Series(close).rolling(20).mean().values

        capital = config.initial_capital
        position = 0.0
        entry_price = 0.0
        entry_date = None
        trades: list[Trade] = []
        equity: list[float] = []
        peak_equity = capital
        drawdowns: list[float] = []
        total_costs = 0.0

        start = rs_lookback_long + 1
        for i in range(start, len(close)):
            price = close[i]
            date = _to_python_datetime(dates[i])

            current_equity = capital + (position * price if position > 0 else 0)
            equity.append(current_equity)
            peak_equity = max(peak_equity, current_equity)
            dd = (peak_equity - current_equity) / peak_equity if peak_equity > 0 else 0
            drawdowns.append(dd)

            # Rolling returns
            stock_ret_short = (close[i] / close[i - rs_lookback_short - 1] - 1) * 100
            bench_ret_short = (bench_close[i] / bench_close[i - rs_lookback_short - 1] - 1) * 100
            stock_ret_long = (close[i] / close[i - rs_lookback_long - 1] - 1) * 100
            bench_ret_long = (bench_close[i] / bench_close[i - rs_lookback_long - 1] - 1) * 100

            rs_short = stock_ret_short - bench_ret_short
            rs_long = stock_ret_long - bench_ret_long

            # Previous RS for acceleration
            stock_ret_short_prev = (close[i - 1] / close[i - rs_lookback_short - 2] - 1) * 100
            bench_ret_short_prev = (bench_close[i - 1] / bench_close[i - rs_lookback_short - 2] - 1) * 100
            rs_short_prev = stock_ret_short_prev - bench_ret_short_prev
            rs_accelerating = rs_short > rs_short_prev

            above_sma = price > sma_20[i] if not np.isnan(sma_20[i]) else True

            # Entry: strong outperformance with acceleration
            if position == 0 and rs_short > 3 and rs_long > 5 and rs_accelerating and above_sma:
                invest = capital * config.position_size_pct
                costs = invest * (config.commission_pct + config.slippage_pct)
                total_costs += costs
                quantity = (invest - costs) / price
                position = quantity
                entry_price = price
                entry_date = date
                capital -= invest

            # Exit: underperforming on both timeframes
            elif position > 0 and rs_short < -2 and rs_long < -3:
                exit_value = position * price
                costs = exit_value * (config.commission_pct + config.slippage_pct)
                total_costs += costs
                net_exit = exit_value - costs
                pnl = net_exit - (position * entry_price)
                trades.append(Trade(
                    entry_date=entry_date, exit_date=date, side="LONG",
                    entry_price=entry_price, exit_price=price,
                    quantity=position, pnl=pnl,
                    pnl_pct=pnl / (position * entry_price) if entry_price > 0 else 0,
                    fees=costs,
                ))
                capital += net_exit
                position = 0.0

            # Exit: close below SMA(20) and RS negative
            elif position > 0 and not above_sma and rs_short < 0:
                exit_value = position * price
                costs = exit_value * (config.commission_pct + config.slippage_pct)
                total_costs += costs
                net_exit = exit_value - costs
                pnl = net_exit - (position * entry_price)
                trades.append(Trade(
                    entry_date=entry_date, exit_date=date, side="LONG",
                    entry_price=entry_price, exit_price=price,
                    quantity=position, pnl=pnl,
                    pnl_pct=pnl / (position * entry_price) if entry_price > 0 else 0,
                    fees=costs,
                ))
                capital += net_exit
                position = 0.0

        if position > 0:
            last_price = close[-1]
            exit_value = position * last_price
            costs = exit_value * (config.commission_pct + config.slippage_pct)
            total_costs += costs
            net_exit = exit_value - costs
            pnl = net_exit - (position * entry_price)
            trades.append(Trade(
                entry_date=entry_date, exit_date=datetime.utcnow(), side="LONG",
                entry_price=entry_price, exit_price=last_price,
                quantity=position, pnl=pnl,
                pnl_pct=pnl / (position * entry_price) if entry_price > 0 else 0,
                fees=costs,
            ))
            capital += net_exit

        result.metrics = _compute_backtest_metrics(
            trades, equity, drawdowns, total_costs, config, dates, start, len(close)
        )
        result.trades = trades
        result.equity_curve = [round(e, 2) for e in equity]
        result.drawdown_curve = [round(d * 100, 2) for d in drawdowns]
        result.timestamps = [_to_python_datetime(dates[i]) for i in range(start, start + len(equity))]
        result.completed_at = datetime.utcnow()

    except Exception as e:
        result.error = str(e)

    return result
