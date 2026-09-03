"""Signal engine — PRD Section 5.

Orchestrates strategy execution, risk gate, and signal persistence.
Generates deterministic, reproducible signals from stored data snapshots.
"""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional

import pandas as pd
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.domain.entities.models import (
    Instrument, MarketBar, Signal, StrategyVersion, DataSnapshot,
    FeatureValue, FeatureDefinition, FundamentalFact,
)
from packages.domain.enums.common import (
    Horizon, SignalState, QualityGate, Timeframe,
)
from packages.strategies.registry.strategy_base import (
    StrategyRegistry, MarketContext, RawSignal,
)
from packages.risk.gate import RiskGate
from packages.risk.confidence import ConfidenceCalculator
from packages.features.indicators.canonical import (
    sma, ema, rsi, macd, bollinger_bands, atr, obv, adx, vwap_rolling,
    session_vwap, volume_rate_of_change, keltner_channels,
)


async def get_bars_for_instrument(
    db: AsyncSession,
    instrument_id: uuid.UUID,
    timeframe: Timeframe = Timeframe.DAILY,
    limit: int = 250,
) -> pd.DataFrame:
    """Fetch bars as a DataFrame for indicator computation."""
    result = await db.execute(
        select(MarketBar)
        .where(
            MarketBar.instrument_id == instrument_id,
            MarketBar.timeframe == timeframe,
        )
        .order_by(MarketBar.ts_open.desc())
        .limit(limit)
    )
    bars = list(reversed(result.scalars().all()))

    if not bars:
        return pd.DataFrame()

    return pd.DataFrame([
        {
            "open": float(b.open),
            "high": float(b.high),
            "low": float(b.low),
            "close": float(b.close),
            "volume": float(b.volume),
            "ts_open": b.ts_open,
        }
        for b in bars
    ])


def get_timeframe_for_horizon(horizon: Horizon) -> Timeframe:
    """Map strategy horizon to appropriate bar timeframe."""
    if horizon == Horizon.INTRADAY:
        return Timeframe.MINUTE_5
    elif horizon == Horizon.SWING:
        return Timeframe.DAILY
    else:  # LONG_TERM
        return Timeframe.DAILY


def compute_indicators(df: pd.DataFrame, timeframe: Timeframe = Timeframe.DAILY) -> dict[str, pd.Series]:
    """Compute all canonical indicators for a bar DataFrame."""
    if df.empty or len(df) < 20:
        return {}

    close = df["close"]
    high = df["high"]
    low = df["low"]
    volume = df["volume"]

    indicators = {}

    # Moving averages
    if len(df) >= 20:
        indicators["sma_20"] = sma(close, 20)
    if len(df) >= 50:
        indicators["sma_50"] = sma(close, 50)
    if len(df) >= 200:
        indicators["sma_200"] = sma(close, 200)
    if len(df) >= 12:
        indicators["ema_12"] = ema(close, 12)
    if len(df) >= 26:
        indicators["ema_26"] = ema(close, 26)

    # Momentum
    if len(df) >= 15:
        indicators["rsi_14"] = rsi(close, 14)

    # Volatility
    if len(df) >= 15:
        indicators["atr_14"] = atr(high, low, close, 14)
    if len(df) >= 20:
        bb = bollinger_bands(close, 20)
        indicators["bb_upper"] = bb.upper
        indicators["bb_middle"] = bb.middle
        indicators["bb_lower"] = bb.lower
        indicators["bb_pct_b"] = bb.pct_b

    # Trend
    if len(df) >= 28:
        indicators["adx_14"] = adx(high, low, close, 14)

    # Volume
    indicators["obv"] = obv(close, volume)

    # Intraday-specific indicators
    if timeframe in (Timeframe.MINUTE_1, Timeframe.MINUTE_5, Timeframe.MINUTE_15, Timeframe.HOURLY):
        if len(df) >= 20:
            indicators["vwap_rolling"] = vwap_rolling(high, low, close, volume, 20)
            indicators["vroc_14"] = volume_rate_of_change(volume, 14)
            kc = keltner_channels(high, low, close, 20, 10, 2.0)
            indicators["kc_upper"] = kc.upper
            indicators["kc_middle"] = kc.middle
            indicators["kc_lower"] = kc.lower
    else:
        # Daily VWAP
        if len(df) >= 20:
            indicators["vwap_rolling"] = vwap_rolling(high, low, close, volume, 20)

    return indicators


async def get_fundamentals(
    db: AsyncSession,
    instrument_id: uuid.UUID,
) -> dict[str, float]:
    """Fetch latest fundamental data for an instrument."""
    result = await db.execute(
        select(FundamentalFact)
        .where(FundamentalFact.instrument_id == instrument_id)
        .order_by(FundamentalFact.created_at.desc())
    )
    facts = result.scalars().all()

    fundamentals = {}
    seen = set()
    for f in facts:
        if f.taxonomy not in seen:
            fundamentals[f.taxonomy] = float(f.value)
            seen.add(f.taxonomy)

    return fundamentals


def is_kill_switch_active() -> bool:
    """Check if the kill switch is active (suppresses all signals)."""
    try:
        from apps.api.routers.admin import _kill_switch_active
        return _kill_switch_active
    except ImportError:
        return False


async def generate_signals_for_instrument(
    db: AsyncSession,
    instrument_id: uuid.UUID,
    strategy_names: Optional[list[str]] = None,
    horizon: Optional[Horizon] = None,
) -> list[dict]:
    """Generate signals for an instrument across all (or filtered) strategies.

    Returns list of signal dicts ready for DB insertion.
    """
    # Check kill switch
    if is_kill_switch_active():
        return [{"strategy": "ALL", "error": "Kill switch active — signal generation suppressed"}]

    # Get instrument
    inst_result = await db.execute(select(Instrument).where(Instrument.id == instrument_id))
    instrument = inst_result.scalar_one_or_none()
    if not instrument or instrument.status.value != "ACTIVE":
        return []

    # Get bars — use appropriate timeframe for horizon
    target_timeframe = get_timeframe_for_horizon(horizon) if horizon else Timeframe.DAILY
    df = await get_bars_for_instrument(db, instrument_id, timeframe=target_timeframe)

    # Fallback to daily if intraday bars not available
    if df.empty and target_timeframe != Timeframe.DAILY:
        df = await get_bars_for_instrument(db, instrument_id, timeframe=Timeframe.DAILY)
        target_timeframe = Timeframe.DAILY

    if df.empty or len(df) < 20:
        return []

    # Compute indicators
    indicators = compute_indicators(df, timeframe=target_timeframe)

    # Get fundamentals
    fundamentals = await get_fundamentals(db, instrument_id)

    # Build market context
    context = MarketContext(
        instrument_id=instrument_id,
        symbol=instrument.symbol,
        bars=df,
        indicators=indicators,
        fundamentals=fundamentals,
        as_of=datetime.utcnow(),
    )

    # Get strategies to run
    if strategy_names:
        strategies = [StrategyRegistry.create(n) for n in strategy_names]
        strategies = [s for s in strategies if s is not None]
    else:
        strategies = [StrategyRegistry.create(c.name) for c in StrategyRegistry.list_all()]
        strategies = [s for s in strategies if s is not None]

    # Filter by horizon
    if horizon:
        strategies = [s for s in strategies if s.metadata.horizon == horizon]

    # Create data snapshot
    snapshot = DataSnapshot(
        source_versions={"bars": "db", "fundamentals": "db"},
        cutoff_ts=datetime.utcnow(),
        hashes={"bars_hash": str(hash(df.to_json()))},
    )
    db.add(snapshot)
    await db.flush()

    # Run each strategy through risk gate
    risk_gate = RiskGate()
    confidence_calc = ConfidenceCalculator()
    signals = []

    for strategy in strategies:
        try:
            raw_signal = strategy.generate(context)

            # Risk gate
            last_bar_ts = df["ts_open"].iloc[-1] if "ts_open" in df.columns else None
            gate_result = risk_gate.evaluate(
                signal=raw_signal,
                instrument_status=instrument.status.value,
                last_bar_ts=last_bar_ts,
                data_completeness=1.0,
                avg_daily_volume=float(df["volume"].tail(20).mean()) if len(df) >= 20 else 0,
                instrument_sector=instrument.sector,
            )

            print(f"[DEBUG] strategy={strategy.metadata.name} state={raw_signal.state} confidence={raw_signal.confidence}", flush=True)

            if raw_signal.state == SignalState.NO_SIGNAL:
                continue

            # Create strategy version record
            strat_version = StrategyVersion(
                name=strategy.metadata.name,
                code_hash=str(hash(strategy.metadata.version)),
                config={"version": strategy.metadata.version, "tags": strategy.metadata.tags},
                horizon=strategy.metadata.horizon,
            )
            db.add(strat_version)
            await db.flush()

            # Calculate deterministic confidence
            conf_result = confidence_calc.calculate(
                strategy_validation_score=0.5,  # default until backtests exist
                regime_similarity=0.5,
                feature_completeness=1.0,
                signal_agreement_count=1,
                total_strategies=len(strategies),
                avg_daily_volume=float(df["volume"].tail(20).mean()) if len(df) >= 20 else 0,
                data_staleness_hours=0,
                model_validated=False,
                parameter_sensitivity_score=0.5,
            )

            # Use the lower of risk gate confidence and calculated confidence
            final_confidence = min(gate_result.adjusted_confidence, conf_result.final_confidence)

            # Compute a generic take-profit target using a 2:1 reward-to-risk
            # ratio off the entry zone and invalidation (stop) level. This is a
            # simple, consistent rule applied uniformly across all strategies —
            # not a strategy-specific target, but a reasonable default so every
            # signal has a concrete profit-taking level.
            target_price = None
            if raw_signal.entry_zone_low and raw_signal.invalidation_level:
                entry_ref = raw_signal.entry_zone_high or raw_signal.entry_zone_low
                risk_per_share = abs(entry_ref - raw_signal.invalidation_level)
                if risk_per_share > 0:
                    if raw_signal.state == SignalState.ENTER_LONG:
                        target_price = entry_ref + (risk_per_share * Decimal("2"))
                    elif raw_signal.state == SignalState.EXIT:
                        target_price = entry_ref - (risk_per_share * Decimal("2"))

            # Create signal record
            signal = Signal(
                instrument_id=instrument_id,
                as_of=datetime.utcnow(),
                horizon=strategy.metadata.horizon,
                state=raw_signal.state,
                entry_zone_low=raw_signal.entry_zone_low,
                entry_zone_high=raw_signal.entry_zone_high,
                invalidation_rule=raw_signal.invalidation_rule,
                invalidation_level=raw_signal.invalidation_level,
                target_method=raw_signal.target_method,
                target_price=target_price,
                max_loss_pct=strategy.risk_plan(raw_signal).max_loss_pct,
                suggested_size_pct=strategy.risk_plan(raw_signal).suggested_size_pct,
                confidence=Decimal(str(final_confidence)),
                quality_gate=gate_result.quality_gate,
                strategy_version_id=strat_version.id,
                data_snapshot_id=snapshot.id,
                evidence_ids=[],
                reason_codes=raw_signal.reason_codes + gate_result.adjustments + [f"confidence_components:{len(conf_result.components)}"],
                limitations=raw_signal.limitations + gate_result.blockers + conf_result.caps_applied,
            )
            db.add(signal)
            signals.append({
                "strategy": strategy.metadata.name,
                "horizon": strategy.metadata.horizon.value,
                "state": raw_signal.state.value,
                "confidence": gate_result.adjusted_confidence,
                "quality_gate": gate_result.quality_gate.value,
                "reason_codes": raw_signal.reason_codes,
                "limitations": raw_signal.limitations,
                "entry_zone": {
                    "low": float(raw_signal.entry_zone_low) if raw_signal.entry_zone_low else None,
                    "high": float(raw_signal.entry_zone_high) if raw_signal.entry_zone_high else None,
                },
                "invalidation": {
                    "rule": raw_signal.invalidation_rule,
                    "level": float(raw_signal.invalidation_level) if raw_signal.invalidation_level else None,
                },
                "target_price": float(target_price) if target_price else None,
            })

        except Exception as e:
            signals.append({
                "strategy": strategy.metadata.name,
                "error": str(e),
            })

    await db.flush()
    return signals
