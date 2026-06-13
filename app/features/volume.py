"""
app/features/volume.py — Volume feature computation.

Computes volume_ratio (latest vs 20-day average), volume trend patterns,
and price-volume interaction flags.

All returned values are Python floats or booleans — never NaN.

Usage:
    from app.features.volume import compute_volume_features
    feats = compute_volume_features(df)
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


def compute_volume_features(df: pd.DataFrame) -> dict:
    """
    Compute volume features from an OHLCV DataFrame.

    Parameters
    ----------
    df : pd.DataFrame
        OHLCV data with a DatetimeIndex. Must have 'Close' and 'Volume' columns.
        Minimum 5 rows required for meaningful volume ratio.

    Returns
    -------
    dict with keys:
        volume_ratio          : float or None  — latest volume / 20d avg volume
        volume_latest         : float or None  — latest bar volume
        volume_avg_20d        : float or None  — 20-day average volume
        volume_up             : bool  — high volume + price up (bullish)
        volume_down           : bool  — high volume + price down (bearish)
        volume_contraction    : bool  — volume_ratio < 0.8 (drying up)
        volume_expansion      : bool  — volume_ratio >= 1.5

    All float values are guaranteed to be non-NaN (None if computation failed).
    """
    if "Volume" not in df.columns:
        return {
            "volume_ratio": None,
            "volume_latest": None,
            "volume_avg_20d": None,
            "volume_up": False,
            "volume_down": False,
            "volume_contraction": False,
            "volume_expansion": False,
        }

    vol_series = df["Volume"].astype(float)
    close_series = df["Close"].astype(float)

    # ── Volume ratio ──────────────────────────────────────────────────────────
    avg_window = min(20, len(vol_series))
    vol_avg = _safe(vol_series.tail(avg_window).mean())
    vol_latest = _safe(vol_series.iloc[-1])

    volume_ratio: Optional[float] = None
    if vol_avg is not None and vol_avg > 0 and vol_latest is not None:
        ratio = vol_latest / vol_avg
        if not (np.isnan(ratio) or np.isinf(ratio)):
            volume_ratio = float(ratio)

    # ── Price direction for last bar ──────────────────────────────────────────
    latest_close = _safe(close_series.iloc[-1]) or 0.0
    prev_close: Optional[float] = None
    if len(close_series) >= 2:
        prev_close = _safe(close_series.iloc[-2])

    price_up = bool(prev_close is not None and latest_close > prev_close)
    price_down = bool(prev_close is not None and latest_close < prev_close)

    # ── Volume pattern flags ──────────────────────────────────────────────────
    high_volume = bool(volume_ratio is not None and volume_ratio >= 1.5)
    volume_up = bool(high_volume and price_up)
    volume_down = bool(high_volume and price_down)
    volume_contraction = bool(volume_ratio is not None and volume_ratio < 0.8)
    volume_expansion = bool(volume_ratio is not None and volume_ratio >= 1.5)

    return {
        "volume_ratio": volume_ratio,
        "volume_latest": vol_latest,
        "volume_avg_20d": vol_avg,
        "volume_up": volume_up,
        "volume_down": volume_down,
        "volume_contraction": volume_contraction,
        "volume_expansion": volume_expansion,
    }
