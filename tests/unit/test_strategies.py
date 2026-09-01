"""Unit tests for strategies — PRD Section 14."""

import uuid
from datetime import datetime
from decimal import Decimal

import numpy as np
import pandas as pd
import pytest

from packages.strategies.registry.strategy_base import (
    StrategyRegistry, MarketContext, RawSignal, SignalState,
)
from packages.strategies.swing.sma_crossover import SMACrossover
from packages.strategies.swing.rsi_reversion import RSIMeanReversion
from packages.strategies.long_term.quality_value import QualityValueComposite
from packages.strategies.intraday.opening_range_breakout import OpeningRangeBreakout
from packages.strategies.intraday.vwap_reclaim import VWAPReclaimRejection
from packages.strategies.intraday.intraday_momentum import IntradayMomentum
from packages.strategies.intraday.volatility_expansion import VolatilityExpansion
from packages.domain.enums.common import Horizon


def make_bars(n: int = 200, trend: str = "up") -> pd.DataFrame:
    """Generate test bar data."""
    np.random.seed(42)
    if trend == "up":
        close = 100 + np.cumsum(np.random.randn(n) * 0.5 + 0.05)
    elif trend == "down":
        close = 100 + np.cumsum(np.random.randn(n) * 0.5 - 0.05)
    else:
        close = 100 + np.cumsum(np.random.randn(n) * 0.5)

    return pd.DataFrame({
        "open": close + np.random.randn(n) * 0.1,
        "high": close + abs(np.random.randn(n) * 0.5),
        "low": close - abs(np.random.randn(n) * 0.5),
        "close": close,
        "volume": np.random.randint(100000, 1000000, n).astype(float),
        "ts_open": pd.date_range("2024-01-01", periods=n, freq="D"),
    })


def make_context(bars: pd.DataFrame, indicators: dict = None) -> MarketContext:
    """Create a MarketContext for testing."""
    from packages.features.indicators.canonical import sma, ema, rsi, atr, bollinger_bands, adx, vwap_rolling

    if indicators is None:
        close = bars["close"]
        high = bars["high"]
        low = bars["low"]
        volume = bars["volume"]
        indicators = {}
        if len(bars) >= 20:
            indicators["sma_20"] = sma(close, 20)
            bb = bollinger_bands(close, 20)
            indicators["bb_upper"] = bb.upper
            indicators["bb_middle"] = bb.middle
            indicators["bb_lower"] = bb.lower
            indicators["bb_pct_b"] = bb.pct_b
            indicators["vwap_rolling"] = vwap_rolling(high, low, close, volume, 20)
        if len(bars) >= 50:
            indicators["sma_50"] = sma(close, 50)
        if len(bars) >= 200:
            indicators["sma_200"] = sma(close, 200)
        if len(bars) >= 12:
            indicators["ema_12"] = ema(close, 12)
        if len(bars) >= 26:
            indicators["ema_26"] = ema(close, 26)
        if len(bars) >= 15:
            indicators["rsi_14"] = rsi(close, 14)
            indicators["atr_14"] = atr(high, low, close, 14)
        if len(bars) >= 28:
            indicators["adx_14"] = adx(high, low, close, 14)

    return MarketContext(
        instrument_id=uuid.uuid4(),
        symbol="TEST",
        bars=bars,
        indicators=indicators,
        fundamentals={"pe_ratio_ttm": 20, "roe": 0.2, "profit_margin": 0.15},
        as_of=datetime.utcnow(),
    )


class TestStrategyRegistry:
    """Test strategy registration and discovery."""

    def test_all_strategies_registered(self):
        cards = StrategyRegistry.list_all()
        assert len(cards) >= 7

    def test_strategies_by_horizon(self):
        swing = StrategyRegistry.list_by_horizon(Horizon.SWING)
        assert len(swing) >= 2

        long_term = StrategyRegistry.list_by_horizon(Horizon.LONG_TERM)
        assert len(long_term) >= 1

        intraday = StrategyRegistry.list_by_horizon(Horizon.INTRADAY)
        assert len(intraday) >= 4

    def test_strategy_creation(self):
        strategy = StrategyRegistry.create("SMACrossover")
        assert strategy is not None
        assert strategy.metadata.horizon == Horizon.SWING

    def test_strategy_not_found(self):
        strategy = StrategyRegistry.create("Nonexistent Strategy")
        assert strategy is None


class TestSMACrossover:
    """Test SMA Crossover strategy."""

    def test_uptrend_generates_signal(self):
        bars = make_bars(60, trend="up")
        context = make_context(bars)
        strategy = SMACrossover()
        signal = strategy.generate(context)
        assert isinstance(signal, RawSignal)
        assert signal.state in SignalState

    def test_insufficient_data_returns_no_signal(self):
        bars = make_bars(10)
        context = make_context(bars)
        strategy = SMACrossover()
        signal = strategy.generate(context)
        assert signal.state == SignalState.NO_SIGNAL

    def test_metadata(self):
        strategy = SMACrossover()
        meta = strategy.metadata
        assert meta.horizon == Horizon.SWING
        assert meta.version == "1.0.0"
        assert len(meta.tags) > 0


class TestRSIMeanReversion:
    """Test RSI Mean Reversion strategy."""

    def test_generates_signal(self):
        bars = make_bars(60)
        context = make_context(bars)
        strategy = RSIMeanReversion()
        signal = strategy.generate(context)
        assert isinstance(signal, RawSignal)

    def test_metadata(self):
        strategy = RSIMeanReversion()
        assert strategy.metadata.horizon == Horizon.SWING


class TestIntradayStrategies:
    """Test all intraday strategies."""

    def test_orb(self):
        bars = make_bars(50)
        context = make_context(bars)
        strategy = OpeningRangeBreakout()
        signal = strategy.generate(context)
        assert isinstance(signal, RawSignal)
        assert strategy.metadata.horizon == Horizon.INTRADAY
        assert "paper-only" in strategy.metadata.tags

    def test_vwap(self):
        bars = make_bars(50)
        context = make_context(bars)
        strategy = VWAPReclaimRejection()
        signal = strategy.generate(context)
        assert isinstance(signal, RawSignal)
        assert strategy.metadata.horizon == Horizon.INTRADAY

    def test_momentum(self):
        bars = make_bars(50)
        context = make_context(bars)
        strategy = IntradayMomentum()
        signal = strategy.generate(context)
        assert isinstance(signal, RawSignal)
        assert strategy.metadata.horizon == Horizon.INTRADAY

    def test_volatility(self):
        bars = make_bars(50)
        context = make_context(bars)
        strategy = VolatilityExpansion()
        signal = strategy.generate(context)
        assert isinstance(signal, RawSignal)
        assert strategy.metadata.horizon == Horizon.INTRADAY

    def test_intraday_strategies_paper_only(self):
        """All intraday strategies should be tagged paper-only."""
        for strategy_cls in [OpeningRangeBreakout, VWAPReclaimRejection, IntradayMomentum, VolatilityExpansion]:
            strategy = strategy_cls()
            assert "paper-only" in strategy.metadata.tags

    def test_intraday_strategies_paper_only(self):
        """All intraday strategies should be tagged paper-only."""
        for strategy_cls in [OpeningRangeBreakout, VWAPReclaimRejection, IntradayMomentum, VolatilityExpansion]:
            strategy = strategy_cls()
            assert "paper-only" in strategy.metadata.tags
