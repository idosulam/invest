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
from packages.domain.entities.models import BacktestRun, MarketBar, Instrument, User
from packages.domain.enums.common import BacktestStatus, Timeframe
from packages.backtest.vectorized.engine import (
    BacktestConfig, run_sma_crossover_backtest, run_rsi_backtest,
)
import pandas as pd

router = APIRouter(prefix="/backtests", tags=["backtests"])


# ── Schemas ─────────────────────────────────────────────────

class BacktestRunRequest(BaseModel):
    instrument_id: uuid.UUID
    strategy: str = "sma_crossover"  # sma_crossover | rsi_reversion
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
    else:
        raise HTTPException(status_code=400, detail=f"Unknown strategy: {req.strategy}")

    # Persist to DB
    db_run = BacktestRun(
        snapshot_id=uuid.uuid4(),  # placeholder
        strategy_version_id=uuid.uuid4(),  # placeholder
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
