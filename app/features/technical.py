"""
app/features/technical.py — Technical indicator feature computation.

Computes: MA5, MA20, MA60 (if enough data), RSI14, MACD(12,26,9),
slopes, crossovers, and cross-indicator flags.

All returned values are Python floats or None — never NaN.
Uses the `ta` library (pip install ta).

Usage:
    from app.features.technical import compute_technical_features
    feats = compute_technical_features(df)
"""

from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd

try:
    from ta.momentum import RSIIndicator
    from ta.trend import MACD, SMAIndicator
    _TA_AVAILABLE = True
except ImportError:
    _TA_AVAILABLE = False


def _safe(value) -> Optional[float]:
    """Convert scalar to float; return None on NaN or error."""
    try:
        v = float(value)
        return None if (np.isnan(v) or np.isinf(v)) else v
    except (TypeError, ValueError):
        return None


def _slope(series: pd.Series, window: int = 5) -> Optional[float]:
    """
    Linear regression slope over the last `window` values of a series.
    Returns None if insufficient non-NaN data.
    """
    tail = series.dropna().tail(window)
    if len(tail) < 2:
        return None
    x = np.arange(len(tail), dtype=float)
    y = tail.values.astype(float)
    # Simple least-squares slope
    x_mean = x.mean()
    y_mean = y.mean()
    denom = ((x - x_mean) ** 2).sum()
    if denom == 0:
        return None
    slope_val = float(((x - x_mean) * (y - y_mean)).sum() / denom)
    if np.isnan(slope_val) or np.isinf(slope_val):
        return None
    return slope_val


def compute_technical_features(df: pd.DataFrame) -> dict:
    """
    Compute technical indicator features from an OHLCV DataFrame.

    Parameters
    ----------
    df : pd.DataFrame
        OHLCV data with a DatetimeIndex. Must have a 'Close' column.
        Minimum 26 rows required for MACD (12/26/9).

    Returns
    -------
    dict with keys:
        ma5               : float or None
        ma20              : float or None
        ma60              : float or None  (None if < 60 rows)
        rsi14             : float or None
        macd_hist         : float or None
        macd_hist_delta   : float or None  (change in macd_hist vs prior bar)
        ma5_slope         : float or None
        ma20_slope        : float or None
        ma5_above_ma20    : bool
        close_above_ma5   : bool
        close_above_ma20  : bool
        ma5_above_ma60    : bool or None  (None if ma60 is None)
        macd_hist_positive: bool
        macd_crossed_up   : bool  (macd_hist flipped negative->positive this bar)
        macd_crossed_down : bool  (macd_hist flipped positive->negative this bar)

    All float values are guaranteed to be non-NaN (None if computation failed).
    """
    if not _TA_AVAILABLE:
        raise ImportError("ta package not installed. Run: pip install ta")

    close = df["Close"].astype(float)

    # ── Moving averages ───────────────────────────────────────────────────────
    ma5_series = SMAIndicator(close, window=5).sma_indicator()
    ma20_series = SMAIndicator(close, window=20).sma_indicator()

    ma5 = _safe(ma5_series.iloc[-1])
    ma20 = _safe(ma20_series.iloc[-1])
    ma60: Optional[float] = None
    if len(close) >= 60:
        ma60_series = SMAIndicator(close, window=60).sma_indicator()
        ma60 = _safe(ma60_series.iloc[-1])

    # ── RSI ───────────────────────────────────────────────────────────────────
    rsi14: Optional[float] = None
    if len(close) >= 15:
        rsi_series = RSIIndicator(close, window=14).rsi()
        rsi14 = _safe(rsi_series.iloc[-1])

    # ── MACD ──────────────────────────────────────────────────────────────────
    macd_hist: Optional[float] = None
    macd_hist_delta: Optional[float] = None
    macd_hist_positive = False
    macd_crossed_up = False
    macd_crossed_down = False

    if len(close) >= 26:
        macd_indicator = MACD(close, window_fast=12, window_slow=26, window_sign=9)
        hist_series = macd_indicator.macd_diff()
        last_hist = _safe(hist_series.iloc[-1])
        prev_hist = _safe(hist_series.iloc[-2]) if len(hist_series) >= 2 else None

        macd_hist = last_hist
        if last_hist is not None and prev_hist is not None:
            macd_hist_delta = last_hist - prev_hist
            macd_hist_positive = last_hist > 0
            # Crossing: previous bar was opposite sign
            if last_hist > 0 and prev_hist <= 0:
                macd_crossed_up = True
            elif last_hist < 0 and prev_hist >= 0:
                macd_crossed_down = True
        elif last_hist is not None:
            macd_hist_positive = last_hist > 0

    # ── Slopes ────────────────────────────────────────────────────────────────
    ma5_slope = _slope(ma5_series, window=5)
    ma20_slope = _slope(ma20_series, window=5)

    # ── Boolean flags ─────────────────────────────────────────────────────────
    latest_close = _safe(close.iloc[-1]) or 0.0

    ma5_above_ma20 = bool(ma5 is not None and ma20 is not None and ma5 > ma20)
    close_above_ma5 = bool(ma5 is not None and latest_close > ma5)
    close_above_ma20 = bool(ma20 is not None and latest_close > ma20)
    ma5_above_ma60: Optional[bool] = None
    if ma5 is not None and ma60 is not None:
        ma5_above_ma60 = bool(ma5 > ma60)

    return {
        "ma5": ma5,
        "ma20": ma20,
        "ma60": ma60,
        "rsi14": rsi14,
        "macd_hist": macd_hist,
        "macd_hist_delta": macd_hist_delta,
        "ma5_slope": ma5_slope,
        "ma20_slope": ma20_slope,
        "ma5_above_ma20": ma5_above_ma20,
        "close_above_ma5": close_above_ma5,
        "close_above_ma20": close_above_ma20,
        "ma5_above_ma60": ma5_above_ma60,
        "macd_hist_positive": macd_hist_positive,
        "macd_crossed_up": macd_crossed_up,
        "macd_crossed_down": macd_crossed_down,
    }
