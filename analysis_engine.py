"""
ART-002: Analysis Engine — WS-2
Computes MA crossover (5/20), RSI (14), MACD (12/26/9) and produces a
composite score (-3 to +3) and signal breakdown per stock.

Dependency note:
    pandas-ta does not support Python 3.10 (latest versions require >=3.11/3.12).
    This module uses the `ta` package (pip install ta) which covers all required
    indicators and is fully compatible with Python 3.10.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

try:
    import ta
    from ta.momentum import RSIIndicator
    from ta.trend import MACD, SMAIndicator
    _TA_AVAILABLE = True
except ImportError:
    _TA_AVAILABLE = False


# ── Data classes ──────────────────────────────────────────────────────────────

@dataclass
class SignalBreakdown:
    """Individual strategy signal result."""
    strategy: str          # "MA_CROSSOVER" | "RSI" | "MACD"
    signal: str            # "BUY" | "SELL" | "HOLD"
    score: int             # +1, 0, or -1
    detail: str            # human-readable detail


@dataclass
class StockAnalysis:
    """Complete analysis result for one stock."""
    ticker: str
    composite_score: int                          # -3 to +3
    recommendation: str                           # "BUY" | "SELL" | "HOLD"
    signals: List[SignalBreakdown] = field(default_factory=list)
    latest_close: Optional[float] = None
    ma5: Optional[float] = None
    ma20: Optional[float] = None
    rsi: Optional[float] = None
    macd_line: Optional[float] = None
    macd_signal: Optional[float] = None
    macd_hist: Optional[float] = None
    error: Optional[str] = None


# ── Signal computation ────────────────────────────────────────────────────────

def _safe_float(value) -> Optional[float]:
    """Convert a value to float; return None on failure."""
    try:
        v = float(value)
        return None if np.isnan(v) else v
    except (TypeError, ValueError):
        return None


def compute_ma_crossover(df: pd.DataFrame) -> SignalBreakdown:
    """
    MA Crossover strategy: 5-day SMA vs 20-day SMA.
    BUY  (+1) : MA5 > MA20  (short-term momentum above long-term)
    SELL (-1) : MA5 < MA20  (short-term momentum below long-term)
    HOLD ( 0) : MA5 == MA20 (rare, treated as neutral)
    """
    close = df["Close"].astype(float)
    ma5 = SMAIndicator(close, window=5).sma_indicator()
    ma20 = SMAIndicator(close, window=20).sma_indicator()

    last_ma5 = _safe_float(ma5.iloc[-1])
    last_ma20 = _safe_float(ma20.iloc[-1])

    if last_ma5 is None or last_ma20 is None:
        return SignalBreakdown("MA_CROSSOVER", "HOLD", 0, "Insufficient data for MA computation")

    if last_ma5 > last_ma20:
        return SignalBreakdown(
            "MA_CROSSOVER", "BUY", +1,
            f"MA5={last_ma5:.2f} > MA20={last_ma20:.2f} — short-term momentum is rising"
        )
    elif last_ma5 < last_ma20:
        return SignalBreakdown(
            "MA_CROSSOVER", "SELL", -1,
            f"MA5={last_ma5:.2f} < MA20={last_ma20:.2f} — short-term momentum is declining"
        )
    else:
        return SignalBreakdown(
            "MA_CROSSOVER", "HOLD", 0,
            f"MA5={last_ma5:.2f} == MA20={last_ma20:.2f} — no directional bias"
        )


def compute_rsi(df: pd.DataFrame, period: int = 14) -> SignalBreakdown:
    """
    RSI strategy: 14-day RSI with 30/70 thresholds.
    BUY  (+1) : RSI < 30  (oversold — potential reversal upward)
    SELL (-1) : RSI > 70  (overbought — potential reversal downward)
    HOLD ( 0) : 30 <= RSI <= 70
    """
    close = df["Close"].astype(float)
    rsi_series = RSIIndicator(close, window=period).rsi()
    last_rsi = _safe_float(rsi_series.iloc[-1])

    if last_rsi is None:
        return SignalBreakdown("RSI", "HOLD", 0, "Insufficient data for RSI computation")

    if last_rsi < 30:
        return SignalBreakdown(
            "RSI", "BUY", +1,
            f"RSI={last_rsi:.1f} < 30 — stock is oversold, buyers may step in"
        )
    elif last_rsi > 70:
        return SignalBreakdown(
            "RSI", "SELL", -1,
            f"RSI={last_rsi:.1f} > 70 — stock is overbought, selling pressure may increase"
        )
    else:
        return SignalBreakdown(
            "RSI", "HOLD", 0,
            f"RSI={last_rsi:.1f} is in neutral zone (30–70)"
        )


def compute_macd(
    df: pd.DataFrame,
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
) -> SignalBreakdown:
    """
    MACD strategy: (12, 26, 9).
    BUY  (+1) : MACD histogram > 0  (MACD line above signal — bullish momentum)
    SELL (-1) : MACD histogram < 0  (MACD line below signal — bearish momentum)
    HOLD ( 0) : histogram == 0
    """
    close = df["Close"].astype(float)
    macd_indicator = MACD(close, window_fast=fast, window_slow=slow, window_sign=signal)
    hist = macd_indicator.macd_diff()
    macd_line = macd_indicator.macd()
    signal_line = macd_indicator.macd_signal()

    last_hist = _safe_float(hist.iloc[-1])
    last_macd = _safe_float(macd_line.iloc[-1])
    last_signal = _safe_float(signal_line.iloc[-1])

    if last_hist is None:
        return SignalBreakdown("MACD", "HOLD", 0, "Insufficient data for MACD computation")

    if last_hist > 0:
        return SignalBreakdown(
            "MACD", "BUY", +1,
            f"MACD={last_macd:.4f}, Signal={last_signal:.4f}, Hist={last_hist:.4f} — upward momentum"
        )
    elif last_hist < 0:
        return SignalBreakdown(
            "MACD", "SELL", -1,
            f"MACD={last_macd:.4f}, Signal={last_signal:.4f}, Hist={last_hist:.4f} — downward momentum"
        )
    else:
        return SignalBreakdown(
            "MACD", "HOLD", 0,
            f"MACD={last_macd:.4f}, Signal={last_signal:.4f}, Hist=0 — no momentum bias"
        )


def _recommendation_from_score(score: int) -> str:
    """Convert composite score to recommendation label."""
    if score >= 2:
        return "BUY"
    elif score <= -2:
        return "SELL"
    else:
        return "HOLD"


# ── Public API ────────────────────────────────────────────────────────────────

def analyse_stock(ticker: str, df: pd.DataFrame) -> StockAnalysis:
    """
    Run all three strategy signals on a single stock DataFrame.

    Parameters
    ----------
    ticker : str          — e.g. '2330.TW'
    df     : pd.DataFrame — OHLCV data (at least 26 rows recommended)

    Returns
    -------
    StockAnalysis with composite_score (-3 to +3) and signal breakdown.
    """
    if not _TA_AVAILABLE:
        return StockAnalysis(
            ticker=ticker,
            composite_score=0,
            recommendation="HOLD",
            error="ta package not installed. Run: pip install ta",
        )

    min_rows = 26  # need at least slow MACD window
    if len(df) < min_rows:
        return StockAnalysis(
            ticker=ticker,
            composite_score=0,
            recommendation="HOLD",
            error=f"Insufficient data: {len(df)} rows (need >={min_rows})",
        )

    try:
        ma_signal = compute_ma_crossover(df)
        rsi_signal = compute_rsi(df)
        macd_signal = compute_macd(df)

        signals = [ma_signal, rsi_signal, macd_signal]
        composite = sum(s.score for s in signals)
        recommendation = _recommendation_from_score(composite)

        # Extract latest indicator values for summary
        close = df["Close"].astype(float)
        ma5_val = _safe_float(SMAIndicator(close, window=5).sma_indicator().iloc[-1])
        ma20_val = _safe_float(SMAIndicator(close, window=20).sma_indicator().iloc[-1])
        rsi_val = _safe_float(RSIIndicator(close, window=14).rsi().iloc[-1])
        _macd = MACD(close, window_fast=12, window_slow=26, window_sign=9)
        macd_line_val = _safe_float(_macd.macd().iloc[-1])
        macd_sig_val = _safe_float(_macd.macd_signal().iloc[-1])
        macd_hist_val = _safe_float(_macd.macd_diff().iloc[-1])

        return StockAnalysis(
            ticker=ticker,
            composite_score=composite,
            recommendation=recommendation,
            signals=signals,
            latest_close=_safe_float(df["Close"].iloc[-1]),
            ma5=ma5_val,
            ma20=ma20_val,
            rsi=rsi_val,
            macd_line=macd_line_val,
            macd_signal=macd_sig_val,
            macd_hist=macd_hist_val,
        )

    except Exception as exc:
        return StockAnalysis(
            ticker=ticker,
            composite_score=0,
            recommendation="HOLD",
            error=str(exc),
        )


def analyse_universe(data: Dict[str, pd.DataFrame]) -> List[StockAnalysis]:
    """
    Analyse all stocks in the data dict.

    Parameters
    ----------
    data : dict  — {ticker: DataFrame} as returned by data_pipeline.fetch_universe()

    Returns
    -------
    List[StockAnalysis] sorted by composite_score descending.
    """
    results = []
    for ticker, df in data.items():
        result = analyse_stock(ticker, df)
        results.append(result)

    results.sort(key=lambda r: r.composite_score, reverse=True)
    return results


def print_analysis_report(results: List[StockAnalysis]) -> None:
    """Print a formatted analysis report to stdout."""
    print(f"\n{'='*65}")
    print(f"{'TICKER':<12} {'SCORE':>6} {'REC':<6} {'MA5':>8} {'MA20':>8} {'RSI':>6}")
    print(f"{'-'*65}")
    for r in results:
        if r.error:
            print(f"{r.ticker:<12} {'ERR':>6} {'—':<6}  {r.error[:30]}")
            continue
        print(
            f"{r.ticker:<12} {r.composite_score:>6} {r.recommendation:<6} "
            f"{r.ma5 or 0:>8.2f} {r.ma20 or 0:>8.2f} {r.rsi or 0:>6.1f}"
        )
    print(f"{'='*65}\n")


# ── Quick smoke test ──────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    import os

    # Allow running standalone; add parent dirs to path if needed
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "ART-001"))

    try:
        from data_pipeline import fetch_universe
    except ImportError:
        print("[analysis_engine] ERROR: cannot import data_pipeline from ART-001")
        sys.exit(1)

    print("=== analysis_engine smoke test ===")
    test_tickers = ["2330.TW", "2454.TW", "2317.TW"]
    data = fetch_universe(tickers=test_tickers, days=60)

    if not data:
        print("[FAIL] No data returned from data_pipeline")
        sys.exit(1)

    results = analyse_universe(data)
    print_analysis_report(results)

    for r in results:
        if r.error:
            print(f"  {r.ticker}: ERROR — {r.error}")
        else:
            print(f"  {r.ticker}: score={r.composite_score}, rec={r.recommendation}")
            for sig in r.signals:
                print(f"    [{sig.strategy}] {sig.signal} ({sig.score:+d}): {sig.detail}")

    print("\n[PASS] analysis_engine smoke test complete")
