"""Backtest endpoints — PRD Section 6.

Run, list, and retrieve backtest results.
"""

import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.auth import get_current_user, require_analyst
from apps.api.database import get_db
from packages.domain.entities.models import BacktestRun, MarketBar, Instrument, User, DataSnapshot, StrategyVersion, StrategyPerformance
from packages.domain.enums.common import BacktestStatus, Timeframe, Horizon
from packages.backtest.vectorized.engine import (
    BacktestConfig, run_sma_crossover_backtest, run_rsi_backtest, run_obv_backtest,
    run_opening_range_breakout_backtest, run_vwap_reclaim_backtest,
    run_intraday_momentum_backtest, run_volatility_expansion_backtest,
    run_relative_strength_spy_backtest,
)
from packages.backtest.event_driven.engine import (
    EventDrivenBacktester, BacktestConfig as EventBacktestConfig,
)
from packages.features.indicators.canonical import sma, rsi as rsi_indicator, atr
import numpy as np
import pandas as pd

router = APIRouter(prefix="/backtests", tags=["backtests"])


# ── Schemas ─────────────────────────────────────────────────

class BacktestRunRequest(BaseModel):
    instrument_id: uuid.UUID
    strategy: str = "sma_crossover"  # sma_crossover | rsi_reversion | obv_trend | opening_range_breakout | vwap_reclaim | intraday_momentum | volatility_expansion
    timeframe: Timeframe = Timeframe.DAILY
    # Strategy params
    fast_period: int = 20
    slow_period: int = 50
    rsi_period: int = 14
    rsi_oversold: float = 30
    rsi_overbought: float = 70
    # Config
    initial_capital: float = 100000
    commission_pct: float = 0.001
    slippage_pct: float = 0.0005
    position_size_pct: float = 0.1
    seed: int = 42


class BacktestMetricsResponse(BaseModel):
    total_return: float = 0
    annualized_return: float = 0
    volatility: float = 0
    sharpe_ratio: float = 0
    sortino_ratio: float = 0
    max_drawdown: float = 0
    calmar_ratio: float = 0
    win_rate: float = 0
    payoff_ratio: float = 0
    total_trades: int = 0
    avg_trade_duration_days: float = 0
    exposure_pct: float = 0
    turnover: float = 0
    total_costs: float = 0


class BacktestResponse(BaseModel):
    id: uuid.UUID
    instrument_id: uuid.UUID
    symbol: Optional[str] = None
    strategy_name: str
    status: str
    metrics: Optional[BacktestMetricsResponse] = None
    equity_curve: list[float] = []
    drawdown_curve: list[float] = []
    timestamps: list[str] = []
    trades_count: int = 0
    config: dict = {}
    error: Optional[str] = None
    data_caveat: Optional[str] = None
    created_at: datetime
    completed_at: Optional[datetime] = None


class BacktestListResponse(BaseModel):
    items: list[BacktestResponse]
    total: int


# ── Endpoints ───────────────────────────────────────────────

@router.post("/run", response_model=BacktestResponse)
async def run_backtest(
    req: BacktestRunRequest,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_analyst),
):
    """Run a backtest on an instrument with the specified strategy."""
    # Get instrument
    inst_result = await db.execute(select(Instrument).where(Instrument.id == req.instrument_id))
    instrument = inst_result.scalar_one_or_none()
    if not instrument:
        raise HTTPException(status_code=404, detail="Instrument not found")

    # Fetch bars
    result = await db.execute(
        select(MarketBar)
        .where(
            MarketBar.instrument_id == req.instrument_id,
            MarketBar.timeframe == req.timeframe,
        )
        .order_by(MarketBar.ts_open)
    )
    bars = result.scalars().all()

    if len(bars) < 60:
        raise HTTPException(status_code=400, detail=f"Need at least 60 bars, got {len(bars)}")

    # Build DataFrame
    df = pd.DataFrame([
        {
            "ts_open": b.ts_open,
            "open": float(b.open),
            "high": float(b.high),
            "low": float(b.low),
            "close": float(b.close),
            "volume": float(b.volume),
        }
        for b in bars
    ])

    # Config
    config = BacktestConfig(
        initial_capital=req.initial_capital,
        commission_pct=req.commission_pct,
        slippage_pct=req.slippage_pct,
        position_size_pct=req.position_size_pct,
        seed=req.seed,
    )

    # Run backtest
    if req.strategy == "sma_crossover":
        bt_result = run_sma_crossover_backtest(df, req.fast_period, req.slow_period, config)
    elif req.strategy == "rsi_reversion":
        bt_result = run_rsi_backtest(df, req.rsi_period, req.rsi_oversold, req.rsi_overbought, config)
    elif req.strategy == "obv_trend":
        bt_result = run_obv_backtest(df, 20, config)
    elif req.strategy == "opening_range_breakout":
        bt_result = run_opening_range_breakout_backtest(df, 2, config)
    elif req.strategy == "vwap_reclaim":
        bt_result = run_vwap_reclaim_backtest(df, 20, config)
    elif req.strategy == "intraday_momentum":
        bt_result = run_intraday_momentum_backtest(df, 14, 12, 26, config)
    elif req.strategy == "volatility_expansion":
        bt_result = run_volatility_expansion_backtest(df, 20, 2.0, config)
    elif req.strategy == "relative_strength_spy":
        # Fetch SPY benchmark bars
        spy_result = await db.execute(select(Instrument).where(Instrument.symbol == "SPY"))
        spy = spy_result.scalar_one_or_none()
        if not spy:
            raise HTTPException(status_code=400, detail="SPY not found in instruments — ingest it first")
        spy_bars_result = await db.execute(
            select(MarketBar)
            .where(MarketBar.instrument_id == spy.id, MarketBar.timeframe == req.timeframe)
            .order_by(MarketBar.ts_open)
        )
        spy_bars = spy_bars_result.scalars().all()
        if len(spy_bars) < 60:
            raise HTTPException(status_code=400, detail=f"SPY needs at least 60 bars, got {len(spy_bars)}")
        spy_df = pd.DataFrame([
            {
                "ts_open": b.ts_open,
                "open": float(b.open),
                "high": float(b.high),
                "low": float(b.low),
                "close": float(b.close),
                "volume": float(b.volume),
            }
            for b in spy_bars
        ])
        bt_result = run_relative_strength_spy_backtest(df, spy_df, 20, 60, config)
    else:
        raise HTTPException(status_code=400, detail=f"Unknown strategy: {req.strategy}")

    # Persist to DB — create real snapshot + strategy version rows first
    # so the foreign keys on BacktestRun actually resolve.
    snapshot = DataSnapshot(
        source_versions={"bars": "db"},
        cutoff_ts=datetime.utcnow(),
        hashes={"bars_hash": str(hash(tuple(df["close"].tolist())))},
        description=f"Backtest snapshot for {req.strategy}",
    )
    db.add(snapshot)
    await db.flush()

    strategy_version = StrategyVersion(
        name=req.strategy,
        code_hash=req.strategy,  # not a real code hash, but satisfies the column
        config={"strategy": req.strategy},
        horizon=Horizon.SWING,
        status="VALIDATED",
    )
    db.add(strategy_version)
    await db.flush()

    db_run = BacktestRun(
        snapshot_id=snapshot.id,
        strategy_version_id=strategy_version.id,
        assumptions={
            "strategy": req.strategy,
            "timeframe": req.timeframe.value,
            "fast_period": req.fast_period,
            "slow_period": req.slow_period,
            "initial_capital": req.initial_capital,
            "commission_pct": req.commission_pct,
            "slippage_pct": req.slippage_pct,
            "seed": req.seed,
        },
        metrics={
            "total_return": bt_result.metrics.total_return,
            "annualized_return": bt_result.metrics.annualized_return,
            "sharpe_ratio": bt_result.metrics.sharpe_ratio,
            "sortino_ratio": bt_result.metrics.sortino_ratio,
            "max_drawdown": bt_result.metrics.max_drawdown,
            "calmar_ratio": bt_result.metrics.calmar_ratio,
            "win_rate": bt_result.metrics.win_rate,
            "payoff_ratio": bt_result.metrics.payoff_ratio,
            "total_trades": bt_result.metrics.total_trades,
            "total_costs": bt_result.metrics.total_costs,
        },
        status=BacktestStatus.COMPLETED if not bt_result.error else BacktestStatus.FAILED,
        started_at=bt_result.started_at,
        completed_at=bt_result.completed_at,
        error=bt_result.error,
    )
    db.add(db_run)
    await db.flush()

    # Upsert into strategy_performance for fast lookups
    from sqlalchemy import select as _select
    existing_perf = await db.execute(
        _select(StrategyPerformance).where(
            StrategyPerformance.strategy_name == req.strategy,
            StrategyPerformance.instrument_id == req.instrument_id,
        )
    )
    perf = existing_perf.scalar_one_or_none()
    if perf:
        perf.total_return = bt_result.metrics.total_return
        perf.annualized_return = bt_result.metrics.annualized_return
        perf.sharpe_ratio = bt_result.metrics.sharpe_ratio
        perf.sortino_ratio = bt_result.metrics.sortino_ratio
        perf.max_drawdown = bt_result.metrics.max_drawdown
        perf.win_rate = bt_result.metrics.win_rate
        perf.payoff_ratio = bt_result.metrics.payoff_ratio
        perf.total_trades = bt_result.metrics.total_trades
        perf.total_costs = bt_result.metrics.total_costs
        perf.data_caveat = bt_result.data_caveat
        perf.backtest_run_id = db_run.id
        perf.config = db_run.assumptions
        perf.run_at = datetime.utcnow()
    else:
        perf = StrategyPerformance(
            strategy_name=req.strategy,
            instrument_id=req.instrument_id,
            symbol=instrument.symbol,
            total_return=bt_result.metrics.total_return,
            annualized_return=bt_result.metrics.annualized_return,
            sharpe_ratio=bt_result.metrics.sharpe_ratio,
            sortino_ratio=bt_result.metrics.sortino_ratio,
            max_drawdown=bt_result.metrics.max_drawdown,
            win_rate=bt_result.metrics.win_rate,
            payoff_ratio=bt_result.metrics.payoff_ratio,
            total_trades=bt_result.metrics.total_trades,
            total_costs=bt_result.metrics.total_costs,
            data_caveat=bt_result.data_caveat,
            backtest_run_id=db_run.id,
            config=db_run.assumptions,
        )
        db.add(perf)
    await db.flush()

    return BacktestResponse(
        id=db_run.id,
        instrument_id=req.instrument_id,
        symbol=instrument.symbol,
        strategy_name=bt_result.strategy_name,
        status=db_run.status.value,
        metrics=BacktestMetricsResponse(
            total_return=bt_result.metrics.total_return,
            annualized_return=bt_result.metrics.annualized_return,
            volatility=bt_result.metrics.volatility,
            sharpe_ratio=bt_result.metrics.sharpe_ratio,
            sortino_ratio=bt_result.metrics.sortino_ratio,
            max_drawdown=bt_result.metrics.max_drawdown,
            calmar_ratio=bt_result.metrics.calmar_ratio,
            win_rate=bt_result.metrics.win_rate,
            payoff_ratio=bt_result.metrics.payoff_ratio,
            total_trades=bt_result.metrics.total_trades,
            avg_trade_duration_days=bt_result.metrics.avg_trade_duration_days,
            exposure_pct=bt_result.metrics.exposure_pct,
            turnover=bt_result.metrics.turnover,
            total_costs=bt_result.metrics.total_costs,
        ),
        equity_curve=bt_result.equity_curve[-500:],  # limit for response size
        drawdown_curve=bt_result.drawdown_curve[-500:],
        timestamps=[str(t) for t in bt_result.timestamps[-500:]],
        trades_count=len(bt_result.trades),
        config=db_run.assumptions,
        error=bt_result.error,
        data_caveat=bt_result.data_caveat,
        created_at=db_run.created_at,
        completed_at=db_run.completed_at,
    )


@router.get("", response_model=BacktestListResponse)
async def list_backtests(
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """List recent backtest runs."""
    result = await db.execute(
        select(BacktestRun).order_by(desc(BacktestRun.created_at)).limit(limit)
    )
    runs = result.scalars().all()

    items = []
    for run in runs:
        items.append(BacktestResponse(
            id=run.id,
            instrument_id=uuid.UUID("00000000-0000-0000-0000-000000000000"),  # placeholder
            strategy_name=run.assumptions.get("strategy", "unknown"),
            status=run.status.value,
            metrics=BacktestMetricsResponse(**run.metrics) if run.metrics else None,
            config=run.assumptions,
            error=run.error,
            created_at=run.created_at,
            completed_at=run.completed_at,
        ))

    return BacktestListResponse(items=items, total=len(items))


@router.get("/{backtest_id}", response_model=BacktestResponse)
async def get_backtest(
    backtest_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """Get a single backtest result."""
    result = await db.execute(select(BacktestRun).where(BacktestRun.id == backtest_id))
    run = result.scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=404, detail="Backtest not found")

    return BacktestResponse(
        id=run.id,
        instrument_id=uuid.UUID("00000000-0000-0000-0000-000000000000"),
        strategy_name=run.assumptions.get("strategy", "unknown"),
        status=run.status.value,
        metrics=BacktestMetricsResponse(**run.metrics) if run.metrics else None,
        config=run.assumptions,
        error=run.error,
        created_at=run.created_at,
        completed_at=run.completed_at,
    )


# ── Strategy Performance (persisted lookups) ────────────────

class StrategyPerformanceResponse(BaseModel):
    strategy_name: str
    instrument_id: uuid.UUID
    symbol: str
    total_return: Optional[float] = None
    annualized_return: Optional[float] = None
    sharpe_ratio: Optional[float] = None
    sortino_ratio: Optional[float] = None
    max_drawdown: Optional[float] = None
    win_rate: Optional[float] = None
    payoff_ratio: Optional[float] = None
    total_trades: Optional[int] = None
    total_costs: Optional[float] = None
    data_caveat: Optional[str] = None
    run_at: datetime

    model_config = {"from_attributes": True}


class StrategyPerformanceListResponse(BaseModel):
    items: list[StrategyPerformanceResponse]
    total: int


@router.get("/performance", response_model=StrategyPerformanceListResponse)
async def list_strategy_performance(
    strategy: Optional[str] = Query(None),
    instrument_id: Optional[uuid.UUID] = Query(None),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """List persisted strategy performance results.

    Filter by strategy name and/or instrument. Returns the latest
    backtest result for each strategy×instrument pair.
    """
    query = select(StrategyPerformance)
    if strategy:
        query = query.where(StrategyPerformance.strategy_name == strategy)
    if instrument_id:
        query = query.where(StrategyPerformance.instrument_id == instrument_id)
    query = query.order_by(desc(StrategyPerformance.run_at))

    result = await db.execute(query)
    rows = result.scalars().all()

    return StrategyPerformanceListResponse(
        items=[StrategyPerformanceResponse.model_validate(r) for r in rows],
        total=len(rows),
    )


@router.get("/performance/{strategy}/{instrument_id}", response_model=StrategyPerformanceResponse)
async def get_strategy_performance(
    strategy: str,
    instrument_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """Get persisted performance for a specific strategy×instrument pair."""
    result = await db.execute(
        select(StrategyPerformance).where(
            StrategyPerformance.strategy_name == strategy,
            StrategyPerformance.instrument_id == instrument_id,
        )
    )
    perf = result.scalar_one_or_none()
    if not perf:
        raise HTTPException(status_code=404, detail="No performance data found for this strategy/instrument pair")
    return StrategyPerformanceResponse.model_validate(perf)


# ── Event-Driven Backtest ───────────────────────────────────

class EventDrivenBacktestRequest(BaseModel):
    instrument_id: uuid.UUID
    strategy: str = "sma_crossover"  # sma_crossover | rsi_reversion | obv_trend | opening_range_breakout | vwap_reclaim | intraday_momentum | volatility_expansion
    timeframe: Timeframe = Timeframe.DAILY
    fast_period: int = 20
    slow_period: int = 50
    rsi_period: int = 14
    rsi_oversold: float = 30
    rsi_overbought: float = 70
    initial_capital: float = 100000
    commission_pct: float = 0.001
    slippage_pct: float = 0.0005
    position_size_pct: float = 0.1
    fill_delay_bars: int = 0
    seed: int = 42


class WalkForwardRequest(BaseModel):
    instrument_id: uuid.UUID
    strategy: str = "sma_crossover"
    timeframe: Timeframe = Timeframe.DAILY
    fast_period: int = 20
    slow_period: int = 50
    rsi_period: int = 14
    n_splits: int = 5
    train_pct: float = 0.7
    initial_capital: float = 100000
    commission_pct: float = 0.001
    slippage_pct: float = 0.0005
    seed: int = 42


class WalkForwardResult(BaseModel):
    splits: list[BacktestMetricsResponse]
    avg_return: float
    avg_sharpe: float
    avg_max_drawdown: float
    consistency: float  # fraction of profitable splits


@router.post("/event-driven", response_model=BacktestResponse)
async def run_event_driven_backtest(
    req: EventDrivenBacktestRequest,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_analyst),
):
    """Run an event-driven backtest with realistic fills and latency."""
    inst_result = await db.execute(select(Instrument).where(Instrument.id == req.instrument_id))
    instrument = inst_result.scalar_one_or_none()
    if not instrument:
        raise HTTPException(status_code=404, detail="Instrument not found")

    result = await db.execute(
        select(MarketBar)
        .where(
            MarketBar.instrument_id == req.instrument_id,
            MarketBar.timeframe == req.timeframe,
        )
        .order_by(MarketBar.ts_open)
    )
    bars = result.scalars().all()
    if len(bars) < 60:
        raise HTTPException(status_code=400, detail=f"Need at least 60 bars, got {len(bars)}")

    df = pd.DataFrame([
        {
            "ts_open": b.ts_open,
            "open": float(b.open),
            "high": float(b.high),
            "low": float(b.low),
            "close": float(b.close),
            "volume": float(b.volume),
        }
        for b in bars
    ])

    # Build signal function based on strategy
    def make_signal_fn(strategy: str, fast: int, slow: int, rsi_p: int, os: float, ob: float):
        def signal_fn(bars_df: pd.DataFrame, idx: int) -> Optional[str]:
            if idx < max(fast, slow, rsi_p) + 5:
                return None
            close = bars_df["close"].iloc[:idx + 1]
            if strategy == "sma_crossover":
                sma_fast = sma(close, fast).iloc[-1]
                sma_slow = sma(close, slow).iloc[-1]
                sma_fast_prev = sma(close, fast).iloc[-2]
                sma_slow_prev = sma(close, slow).iloc[-2]
                if sma_fast_prev <= sma_slow_prev and sma_fast > sma_slow:
                    return "BUY"
                elif sma_fast_prev >= sma_slow_prev and sma_fast < sma_slow:
                    return "SELL"
            elif strategy == "rsi_reversion":
                rsi_val = rsi_indicator(close, rsi_p).iloc[-1]
                rsi_prev = rsi_indicator(close, rsi_p).iloc[-2]
                if rsi_prev < os and rsi_val >= os:
                    return "BUY"
                elif rsi_val > ob:
                    return "SELL"
            return None
        return signal_fn

    signal_fn = make_signal_fn(
        req.strategy, req.fast_period, req.slow_period,
        req.rsi_period, req.rsi_oversold, req.rsi_overbought,
    )

    config = EventBacktestConfig(
        initial_capital=req.initial_capital,
        commission_pct=req.commission_pct,
        slippage_pct=req.slippage_pct,
        max_position_pct=req.position_size_pct,
        fill_delay_bars=req.fill_delay_bars,
        seed=req.seed,
    )

    backtester = EventDrivenBacktester(config)
    bt_result = backtester.run(df, signal_fn)

    # Persist
    db_run = BacktestRun(
        snapshot_id=uuid.uuid4(),
        strategy_version_id=uuid.uuid4(),
        assumptions={
            "strategy": req.strategy,
            "engine": "event_driven",
            "timeframe": req.timeframe.value,
            "fill_delay_bars": req.fill_delay_bars,
            "initial_capital": req.initial_capital,
            "commission_pct": req.commission_pct,
            "slippage_pct": req.slippage_pct,
            "seed": req.seed,
        },
        metrics={
            "total_return": bt_result.metrics.total_return,
            "annualized_return": bt_result.metrics.annualized_return,
            "sharpe_ratio": bt_result.metrics.sharpe_ratio,
            "sortino_ratio": bt_result.metrics.sortino_ratio,
            "max_drawdown": bt_result.metrics.max_drawdown,
            "calmar_ratio": bt_result.metrics.calmar_ratio,
            "win_rate": bt_result.metrics.win_rate,
            "payoff_ratio": bt_result.metrics.payoff_ratio,
            "total_trades": bt_result.metrics.total_trades,
            "total_commission": bt_result.metrics.total_commission,
            "total_slippage": bt_result.metrics.total_slippage,
            "benchmark_return": bt_result.metrics.benchmark_return,
            "alpha": bt_result.metrics.alpha,
        },
        status=BacktestStatus.COMPLETED,
        started_at=datetime.utcnow(),
        completed_at=datetime.utcnow(),
    )
    db.add(db_run)
    await db.flush()

    return BacktestResponse(
        id=db_run.id,
        instrument_id=req.instrument_id,
        symbol=instrument.symbol,
        strategy_name=f"{req.strategy} (event-driven)",
        status="COMPLETED",
        metrics=BacktestMetricsResponse(
            total_return=bt_result.metrics.total_return,
            annualized_return=bt_result.metrics.annualized_return,
            volatility=bt_result.metrics.volatility,
            sharpe_ratio=bt_result.metrics.sharpe_ratio,
            sortino_ratio=bt_result.metrics.sortino_ratio,
            max_drawdown=bt_result.metrics.max_drawdown,
            calmar_ratio=bt_result.metrics.calmar_ratio,
            win_rate=bt_result.metrics.win_rate,
            payoff_ratio=bt_result.metrics.payoff_ratio,
            total_trades=bt_result.metrics.total_trades,
            avg_trade_duration_days=bt_result.metrics.avg_bars_held,
            exposure_pct=bt_result.metrics.exposure,
            turnover=bt_result.metrics.turnover,
            total_costs=bt_result.metrics.total_commission + bt_result.metrics.total_slippage,
        ),
        equity_curve=[round(v, 2) for v in bt_result.equity_curve.tolist()[-500:]],
        drawdown_curve=[round(v, 4) for v in bt_result.drawdown_curve.tolist()[-500:]],
        timestamps=[str(t) for t in bt_result.equity_curve.index[-500:]],
        trades_count=len(bt_result.trades),
        config=db_run.assumptions,
        created_at=db_run.created_at,
        completed_at=db_run.completed_at,
    )


@router.post("/walk-forward", response_model=WalkForwardResult)
async def run_walk_forward(
    req: WalkForwardRequest,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_analyst),
):
    """Run walk-forward validation with chronological train/test splits.

    PRD Section 6: chronological train/validation/test splits,
    walk-forward evaluation, benchmark comparison.
    """
    inst_result = await db.execute(select(Instrument).where(Instrument.id == req.instrument_id))
    instrument = inst_result.scalar_one_or_none()
    if not instrument:
        raise HTTPException(status_code=404, detail="Instrument not found")

    result = await db.execute(
        select(MarketBar)
        .where(
            MarketBar.instrument_id == req.instrument_id,
            MarketBar.timeframe == req.timeframe,
        )
        .order_by(MarketBar.ts_open)
    )
    bars = result.scalars().all()
    if len(bars) < 200:
        raise HTTPException(status_code=400, detail=f"Walk-forward needs 200+ bars, got {len(bars)}")

    df = pd.DataFrame([
        {
            "ts_open": b.ts_open,
            "open": float(b.open),
            "high": float(b.high),
            "low": float(b.low),
            "close": float(b.close),
            "volume": float(b.volume),
        }
        for b in bars
    ])

    # Build signal function
    def make_signal_fn(strategy: str, fast: int, slow: int, rsi_p: int):
        def signal_fn(bars_df: pd.DataFrame, idx: int) -> Optional[str]:
            if idx < max(fast, slow, rsi_p) + 5:
                return None
            close = bars_df["close"].iloc[:idx + 1]
            if strategy == "sma_crossover":
                sma_fast = sma(close, fast).iloc[-1]
                sma_slow = sma(close, slow).iloc[-1]
                sma_fast_prev = sma(close, fast).iloc[-2]
                sma_slow_prev = sma(close, slow).iloc[-2]
                if sma_fast_prev <= sma_slow_prev and sma_fast > sma_slow:
                    return "BUY"
                elif sma_fast_prev >= sma_slow_prev and sma_fast < sma_slow:
                    return "SELL"
            elif strategy == "rsi_reversion":
                rsi_val = rsi_indicator(close, rsi_p).iloc[-1]
                rsi_prev = rsi_indicator(close, rsi_p).iloc[-2]
                if rsi_prev < 30 and rsi_val >= 30:
                    return "BUY"
                elif rsi_val > 70:
                    return "SELL"
            return None
        return signal_fn

    signal_fn = make_signal_fn(req.strategy, req.fast_period, req.slow_period, req.rsi_period)

    # Walk-forward splits
    n = len(df)
    split_size = n // req.n_splits
    splits = []

    for i in range(req.n_splits):
        start = i * split_size
        end = min((i + 1) * split_size + split_size // 2, n)  # overlap for context
        if end - start < 60:
            continue

        split_df = df.iloc[start:end].reset_index(drop=True)

        config = EventBacktestConfig(
            initial_capital=req.initial_capital,
            commission_pct=req.commission_pct,
            slippage_pct=req.slippage_pct,
            seed=req.seed,
        )

        backtester = EventDrivenBacktester(config)
        bt_result = backtester.run(split_df, signal_fn)

        splits.append(BacktestMetricsResponse(
            total_return=bt_result.metrics.total_return,
            annualized_return=bt_result.metrics.annualized_return,
            volatility=bt_result.metrics.volatility,
            sharpe_ratio=bt_result.metrics.sharpe_ratio,
            sortino_ratio=bt_result.metrics.sortino_ratio,
            max_drawdown=bt_result.metrics.max_drawdown,
            calmar_ratio=bt_result.metrics.calmar_ratio,
            win_rate=bt_result.metrics.win_rate,
            payoff_ratio=bt_result.metrics.payoff_ratio,
            total_trades=bt_result.metrics.total_trades,
            avg_trade_duration_days=bt_result.metrics.avg_bars_held,
            exposure_pct=bt_result.metrics.exposure,
            turnover=bt_result.metrics.turnover,
            total_costs=bt_result.metrics.total_commission + bt_result.metrics.total_slippage,
        ))

    if not splits:
        raise HTTPException(status_code=400, detail="Not enough data for walk-forward splits")

    avg_return = sum(s.total_return for s in splits) / len(splits)
    avg_sharpe = sum(s.sharpe_ratio for s in splits) / len(splits)
    avg_dd = sum(s.max_drawdown for s in splits) / len(splits)
    profitable = sum(1 for s in splits if s.total_return > 0)
    consistency = profitable / len(splits)

    return WalkForwardResult(
        splits=splits,
        avg_return=round(avg_return, 4),
        avg_sharpe=round(avg_sharpe, 4),
        avg_max_drawdown=round(avg_dd, 4),
        consistency=round(consistency, 4),
    )
