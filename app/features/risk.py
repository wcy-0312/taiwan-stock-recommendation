"""
app/features/risk.py — Risk feature computation.

Computes ATR14 (Average True Range), ATR%, support/resistance levels,
and distance-to-support/resistance metrics.

All returned values are Python floats or booleans — never NaN.

Usage:
    from app.features.risk import compute_risk_features
    feats = compute_risk_features(df)
"""

from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd


def _safe(value) -> Optional[float]:
    """Convert scalar to float; return None on NaN or error."""
    try:
        v = float(value)
        return None if (np.isnan(v) or np.isinf(v)) else v
    except (TypeError, ValueError):
        return None


def _compute_atr(df: pd.DataFrame, window: int = 14) -> Optional[float]:
    """
    Compute ATR (Average True Range) using Wilder's smoothing.

    True Range = max(High-Low, |High-PrevClose|, |Low-PrevClose|)
    ATR = simple average of TR over `window` periods.

    Returns None if insufficient data or columns missing.
    """
    needed = {"High", "Low", "Close"}
    if not needed.issubset(df.columns):
        return None
    if len(df) < 2:
        return None

    high = df["High"].astype(float)
    low = df["Low"].astype(float)
    close = df["Close"].astype(float)
    prev_close = close.shift(1)

    tr1 = (high - low).abs()
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()
    true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

    atr_window = min(window, len(true_range.dropna()))
    if atr_window < 1:
        return None

    atr_val = _safe(true_range.dropna().tail(atr_window).mean())
    return atr_val


def compute_risk_features(df: pd.DataFrame) -> dict:
    """
    Compute risk features from an OHLCV DataFrame.

    Parameters
    ----------
    df : pd.DataFrame
        OHLCV data with a DatetimeIndex. Must have High, Low, Close columns.
        Minimum 5 rows required; 20 rows recommended for support/resistance.

    Returns
    -------
    dict with keys:
        atr14                  : float or None  — 14-period ATR in price units
        atr_pct                : float or None  — ATR as % of latest close
        support_20d            : float or None  — 20-day low (support level)
        resistance_20d         : float or None  — 20-day high (resistance level)
        dist_to_support_pct    : float or None  — % above support
        dist_to_resistance_pct : float or None  — % below resistance
        near_resistance        : bool  — dist_to_resistance_pct < 3%
        broke_support          : bool  — latest close < support_20d

    All float values are guaranteed to be non-NaN (None if computation failed).
    """
    close_series = df["Close"].astype(float)
    latest_close = _safe(close_series.iloc[-1])

    # ── ATR ───────────────────────────────────────────────────────────────────
    atr14 = _compute_atr(df, window=14)
    atr_pct: Optional[float] = None
    if atr14 is not None and latest_close is not None and latest_close > 0:
        atr_pct = float(atr14 / latest_close * 100)
        if np.isnan(atr_pct) or np.isinf(atr_pct):
            atr_pct = None

    # ── Support / Resistance (20-day) ─────────────────────────────────────────
    window_20 = min(20, len(df))
    support_20d: Optional[float] = None
    resistance_20d: Optional[float] = None

    if "Low" in df.columns and "High" in df.columns:
        low_series = df["Low"].astype(float)
        high_series = df["High"].astype(float)
        support_20d = _safe(low_series.tail(window_20).min())
        resistance_20d = _safe(high_series.tail(window_20).max())

    # ── Distance metrics ──────────────────────────────────────────────────────
    dist_to_support_pct: Optional[float] = None
    dist_to_resistance_pct: Optional[float] = None
    near_resistance = False
    broke_support = False

    if latest_close is not None and latest_close > 0:
        if support_20d is not None and support_20d > 0:
            d = float((latest_close - support_20d) / support_20d * 100)
            if not (np.isnan(d) or np.isinf(d)):
                dist_to_support_pct = d
            broke_support = bool(latest_close < support_20d)

        if resistance_20d is not None and resistance_20d > 0:
            d = float((resistance_20d - latest_close) / resistance_20d * 100)
            if not (np.isnan(d) or np.isinf(d)):
                dist_to_resistance_pct = d
            near_resistance = bool(
                dist_to_resistance_pct is not None and dist_to_resistance_pct < 3.0
            )

    return {
        "atr14": atr14,
        "atr_pct": atr_pct,
        "support_20d": support_20d,
        "resistance_20d": resistance_20d,
        "dist_to_support_pct": dist_to_support_pct,
        "dist_to_resistance_pct": dist_to_resistance_pct,
        "near_resistance": near_resistance,
        "broke_support": broke_support,
    }
