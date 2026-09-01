"""Canonical technical indicators — PRD Section 5.2 (strategy families).

All indicators are pure functions operating on pandas Series/DataFrames.
No future data leakage: each calculation uses only data available at or
before the current bar (left-closed, right-closed windows).

Implements: SMA, EMA, RSI, MACD, Bollinger Bands, ATR, VWAP, OBV.
"""

from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

import numpy as np
import pandas as pd


# ── Result containers ───────────────────────────────────────

@dataclass
class MACDResult:
    macd: pd.Series
    signal: pd.Series
    histogram: pd.Series


@dataclass
class BollingerResult:
    upper: pd.Series
    middle: pd.Series
    lower: pd.Series
    bandwidth: pd.Series
    pct_b: pd.Series


# ── Moving Averages ─────────────────────────────────────────

def sma(series: pd.Series, period: int) -> pd.Series:
    """Simple Moving Average.

    Args:
        series: Price series (typically close).
        period: Number of bars for the window.

    Returns:
        SMA series with NaN for initial (period-1) bars.
    """
    return series.rolling(window=period, min_periods=period).mean()


def ema(series: pd.Series, period: int, adjust: bool = False) -> pd.Series:
    """Exponential Moving Average.

    Args:
        series: Price series.
        period: Span for the EMA.
        adjust: pandas adjust parameter (False = recursive formula).

    Returns:
        EMA series.
    """
    return series.ewm(span=period, adjust=adjust).mean()


def wma(series: pd.Series, period: int) -> pd.Series:
    """Weighted Moving Average (linear weights)."""
    weights = np.arange(1, period + 1, dtype=float)
    return series.rolling(window=period).apply(
        lambda x: np.dot(x, weights) / weights.sum(), raw=True
    )


# ── Momentum ────────────────────────────────────────────────

def rsi(series: pd.Series, period: int = 14) -> pd.Series:
    """Relative Strength Index (Wilder's smoothing).

    Args:
        series: Close price series.
        period: Lookback period (default 14).

    Returns:
        RSI values in [0, 100].
    """
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = (-delta).clip(lower=0)

    # Wilder's smoothing (equivalent to EMA with alpha=1/period)
    avg_gain = gain.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()

    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def macd(
    series: pd.Series,
    fast: int = 12,
    slow: int = 26,
    signal_period: int = 9,
) -> MACDResult:
    """MACD (Moving Average Convergence Divergence).

    Args:
        series: Close price series.
        fast: Fast EMA period (default 12).
        slow: Slow EMA period (default 26).
        signal_period: Signal line EMA period (default 9).

    Returns:
        MACDResult with macd, signal, histogram series.
    """
    fast_ema = ema(series, fast)
    slow_ema = ema(series, slow)
    macd_line = fast_ema - slow_ema
    signal_line = ema(macd_line, signal_period)
    histogram = macd_line - signal_line

    return MACDResult(macd=macd_line, signal=signal_line, histogram=histogram)


# ── Volatility ──────────────────────────────────────────────

def bollinger_bands(
    series: pd.Series,
    period: int = 20,
    std_dev: float = 2.0,
) -> BollingerResult:
    """Bollinger Bands.

    Args:
        series: Close price series.
        period: SMA window (default 20).
        std_dev: Standard deviation multiplier (default 2.0).

    Returns:
        BollingerResult with upper, middle, lower, bandwidth, pct_b.
    """
    middle = sma(series, period)
    rolling_std = series.rolling(window=period, min_periods=period).std()

    upper = middle + (std_dev * rolling_std)
    lower = middle - (std_dev * rolling_std)

    bandwidth = (upper - lower) / middle
    pct_b = (series - lower) / (upper - lower)

    return BollingerResult(
        upper=upper, middle=middle, lower=lower,
        bandwidth=bandwidth, pct_b=pct_b,
    )


def atr(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    period: int = 14,
) -> pd.Series:
    """Average True Range (Wilder's smoothing).

    Args:
        high: High price series.
        low: Low price series.
        close: Close price series.
        period: Lookback period (default 14).

    Returns:
        ATR series.
    """
    prev_close = close.shift(1)
    tr1 = high - low
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()
    true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

    return true_range.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()


# ── Volume ──────────────────────────────────────────────────

def obv(close: pd.Series, volume: pd.Series) -> pd.Series:
    """On-Balance Volume.

    Cumulative volume: add on up-close, subtract on down-close.
    """
    direction = np.sign(close.diff())
    direction.iloc[0] = 0
    return (volume * direction).cumsum()


def vwap_rolling(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    volume: pd.Series,
    period: int = 20,
) -> pd.Series:
    """Rolling VWAP (Volume-Weighted Average Price).

    Args:
        high, low, close: Price series.
        volume: Volume series.
        period: Rolling window (default 20).

    Returns:
        Rolling VWAP series.
    """
    typical_price = (high + low + close) / 3
    tp_vol = typical_price * volume
    return tp_vol.rolling(window=period).sum() / volume.rolling(window=period).sum()


# ── Trend ───────────────────────────────────────────────────

def adx(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    period: int = 14,
) -> pd.Series:
    """Average Directional Index.

    Args:
        high, low, close: Price series.
        period: Lookback period (default 14).

    Returns:
        ADX series (0-100).
    """
    plus_dm = high.diff()
    minus_dm = -low.diff()

    plus_dm = plus_dm.where((plus_dm > minus_dm) & (plus_dm > 0), 0.0)
    minus_dm = minus_dm.where((minus_dm > plus_dm) & (minus_dm > 0), 0.0)

    atr_val = atr(high, low, close, period)

    plus_di = 100 * (plus_dm.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean() / atr_val)
    minus_di = 100 * (minus_dm.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean() / atr_val)

    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di)
    return dx.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()


def supertrend(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    period: int = 10,
    multiplier: float = 3.0,
) -> pd.Series:
    """Supertrend indicator.

    Returns:
        Supertrend line. Values below close = uptrend, above = downtrend.
    """
    atr_val = atr(high, low, close, period)
    hl2 = (high + low) / 2

    upper_band = hl2 + (multiplier * atr_val)
    lower_band = hl2 - (multiplier * atr_val)

    supertrend_line = pd.Series(index=close.index, dtype=float)
    direction = pd.Series(index=close.index, dtype=int)

    supertrend_line.iloc[0] = upper_band.iloc[0]
    direction.iloc[0] = -1

    for i in range(1, len(close)):
        if close.iloc[i] > upper_band.iloc[i - 1]:
            direction.iloc[i] = 1
        elif close.iloc[i] < lower_band.iloc[i - 1]:
            direction.iloc[i] = -1
        else:
            direction.iloc[i] = direction.iloc[i - 1]

        if direction.iloc[i] == 1:
            supertrend_line.iloc[i] = max(lower_band.iloc[i], supertrend_line.iloc[i - 1]) \
                if direction.iloc[i - 1] == 1 else lower_band.iloc[i]
        else:
            supertrend_line.iloc[i] = min(upper_band.iloc[i], supertrend_line.iloc[i - 1]) \
                if direction.iloc[i - 1] == -1 else upper_band.iloc[i]

    return supertrend_line


# ── Convenience: compute all canonical indicators at once ───

@dataclass
class IndicatorSet:
    """All canonical indicators for a single instrument."""
    sma_20: pd.Series
    sma_50: pd.Series
    sma_200: pd.Series
    ema_12: pd.Series
    ema_26: pd.Series
    rsi_14: pd.Series
    macd: MACDResult
    bollinger: BollingerResult
    atr_14: pd.Series
    obv: pd.Series
    adx_14: pd.Series


def compute_all(df: pd.DataFrame) -> IndicatorSet:
    """Compute all canonical indicators from a DataFrame with OHLCV columns.

    Args:
        df: DataFrame with columns: open, high, low, close, volume.

    Returns:
        IndicatorSet with all computed indicators.
    """
    close = df["close"]
    high = df["high"]
    low = df["low"]
    volume = df["volume"]

    return IndicatorSet(
        sma_20=sma(close, 20),
        sma_50=sma(close, 50),
        sma_200=sma(close, 200),
        ema_12=ema(close, 12),
        ema_26=ema(close, 26),
        rsi_14=rsi(close, 14),
        macd=macd(close),
        bollinger=bollinger_bands(close),
        atr_14=atr(high, low, close, 14),
        obv=obv(close, volume),
        adx_14=adx(high, low, close, 14),
    )
