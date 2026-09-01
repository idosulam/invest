"""Unit tests for technical indicators — PRD Section 5.2."""

import numpy as np
import pandas as pd
import pytest

from packages.features.indicators.canonical import (
    sma, ema, wma, rsi, macd, bollinger_bands, atr, obv,
    vwap_rolling, adx, supertrend, session_vwap, opening_range,
    volume_rate_of_change, keltner_channels, intraday_momentum_index,
)


def make_prices(n: int = 100) -> pd.Series:
    """Generate test price series."""
    np.random.seed(42)
    return pd.Series(100 + np.cumsum(np.random.randn(n) * 0.5))


def make_ohlcv(n: int = 100) -> pd.DataFrame:
    """Generate test OHLCV data."""
    np.random.seed(42)
    close = 100 + np.cumsum(np.random.randn(n) * 0.5)
    return pd.DataFrame({
        "open": close + np.random.randn(n) * 0.1,
        "high": close + abs(np.random.randn(n) * 0.5),
        "low": close - abs(np.random.randn(n) * 0.5),
        "close": close,
        "volume": np.random.randint(100000, 1000000, n),
    })


class TestMovingAverages:
    """Test SMA, EMA, WMA."""

    def test_sma(self):
        prices = make_prices(50)
        result = sma(prices, 20)
        assert len(result) == 50
        assert result.isna().sum() == 19  # first 19 are NaN
        assert not result.iloc[-1] != result.iloc[-1]  # not NaN

    def test_ema(self):
        prices = make_prices(50)
        result = ema(prices, 20)
        assert len(result) == 50
        assert not result.iloc[-1] != result.iloc[-1]

    def test_wma(self):
        prices = make_prices(50)
        result = wma(prices, 20)
        assert len(result) == 50


class TestMomentum:
    """Test RSI, MACD."""

    def test_rsi_bounds(self):
        prices = make_prices(100)
        result = rsi(prices, 14)
        valid = result.dropna()
        assert (valid >= 0).all()
        assert (valid <= 100).all()

    def test_rsi_period(self):
        prices = make_prices(100)
        result = rsi(prices, 14)
        assert result.isna().sum() >= 14

    def test_macd(self):
        prices = make_prices(100)
        result = macd(prices)
        assert len(result.macd) == 100
        assert len(result.signal) == 100
        assert len(result.histogram) == 100


class TestVolatility:
    """Test Bollinger Bands, ATR."""

    def test_bollinger_bands(self):
        prices = make_prices(100)
        result = bollinger_bands(prices, 20)
        assert len(result.upper) == 100
        assert len(result.lower) == 100
        # Upper > Middle > Lower
        valid_idx = result.upper.dropna().index
        assert (result.upper[valid_idx] >= result.middle[valid_idx]).all()
        assert (result.middle[valid_idx] >= result.lower[valid_idx]).all()

    def test_atr(self):
        df = make_ohlcv(100)
        result = atr(df["high"], df["low"], df["close"], 14)
        valid = result.dropna()
        assert (valid >= 0).all()


class TestVolume:
    """Test OBV, VWAP."""

    def test_obv(self):
        df = make_ohlcv(100)
        result = obv(df["close"], df["volume"])
        assert len(result) == 100

    def test_vwap_rolling(self):
        df = make_ohlcv(100)
        result = vwap_rolling(df["high"], df["low"], df["close"], df["volume"], 20)
        valid = result.dropna()
        assert (valid > 0).all()


class TestTrend:
    """Test ADX, Supertrend."""

    def test_adx(self):
        df = make_ohlcv(100)
        result = adx(df["high"], df["low"], df["close"], 14)
        valid = result.dropna()
        assert (valid >= 0).all()
        assert (valid <= 100).all()

    def test_supertrend(self):
        df = make_ohlcv(100)
        result = supertrend(df["high"], df["low"], df["close"])
        assert len(result) == 100


class TestIntradayIndicators:
    """Test intraday-specific indicators."""

    def test_session_vwap(self):
        df = make_ohlcv(100)
        result = session_vwap(df["high"], df["low"], df["close"], df["volume"])
        valid = result.dropna()
        assert (valid > 0).all()

    def test_volume_rate_of_change(self):
        df = make_ohlcv(100)
        result = volume_rate_of_change(df["volume"], 14)
        valid = result.dropna()
        assert (valid > 0).all()

    def test_keltner_channels(self):
        df = make_ohlcv(100)
        result = keltner_channels(df["high"], df["low"], df["close"])
        valid = result.upper.dropna().index
        assert (result.upper[valid] >= result.middle[valid]).all()

    def test_intraday_momentum_index(self):
        prices = make_prices(100)
        result = intraday_momentum_index(prices, 14)
        valid = result.dropna()
        assert (valid >= 0).all()
        assert (valid <= 100).all()
