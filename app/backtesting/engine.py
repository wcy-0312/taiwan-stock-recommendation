"""
app/backtesting/engine.py — Walk-forward backtest engine.

Strategy:
  On each trading day in [start, end], run the full radar scoring on
  historical OHLCV data available up to that day.  Enter the top-N
  bullish stocks (by radar score / base_score) and exit after
  `holding_days` trading days.  Collect per-trade returns and pass
  to metrics.py for summary statistics.

Design rules:
  - Uses ONLY data available on the entry date (no look-ahead).
  - Fetches full historical range from yfinance once per ticker (cached).
  - Skips DELISTED_TICKERS (2888.TW).
  - Min sample: 10 trades; otherwise returns "歷史樣本不足" in report.
  - No fractional shares; return is simple price change %.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

import pandas as pd
import yfinance as yf

from app.config import DELISTED_TICKERS
from app.features.technical import compute_technical_features
from app.features.volume import compute_volume_features
from app.features.risk import compute_risk_features
from app.scoring.radar import (
    compute_trend_score,
    compute_momentum_score,
    compute_volume_score,
    compute_risk_score,
)
from app.backtesting.metrics import compute_metrics, format_metrics_report


# ── Data class for a single trade record ─────────────────────────────────────

@dataclass
class TradeRecord:
    """One closed trade in the backtest."""
    ticker: str
    entry_date: str       # YYYY-MM-DD
    exit_date: str        # YYYY-MM-DD
    entry_price: float
    exit_price: float
    return_pct: float     # (exit - entry) / entry * 100


# ── Raw OHLCV fetcher (no scoring cache, only price data) ─────────────────────

def _fetch_full_history(
    ticker: str,
    start: str,
    end: str,
    batch_delay: float = 0.2,
) -> Optional[pd.DataFrame]:
    """
    Fetch full OHLCV history for a ticker over the backtest range.

    Returns a DataFrame indexed by DatetimeIndex (tz-naive),
    or None if the ticker is delisted or data is unavailable.

    We fetch a wider window (start - 120 days) so that indicators
    computed at the start date have enough lookback data.
    """
    if ticker in DELISTED_TICKERS:
        return None

    # Wide fetch: extra 120 calendar days before start for indicator warmup
    start_dt = datetime.strptime(start, "%Y-%m-%d") - timedelta(days=120)
    end_dt = datetime.strptime(end, "%Y-%m-%d") + timedelta(days=5)  # inclusive buffer

    try:
        raw = yf.download(
            ticker,
            start=start_dt.strftime("%Y-%m-%d"),
            end=end_dt.strftime("%Y-%m-%d"),
            auto_adjust=True,
            progress=False,
        )
    except Exception as exc:
        print(f"[backtest.engine] WARNING: yfinance download failed for {ticker}: {exc}")
        return None

    if raw is None or raw.empty:
        return None

    # Normalise MultiIndex columns
    if isinstance(raw.columns, pd.MultiIndex):
        raw.columns = raw.columns.get_level_values(0)

    needed = [c for c in ["Open", "High", "Low", "Close", "Volume"] if c in raw.columns]
    df = raw[needed].copy()
    df.index = pd.to_datetime(df.index).tz_localize(None)
    df.index.name = "Date"
    df = df.dropna(subset=["Close"])

    if len(df) < 26:
        return None

    return df


def _compute_base_score(df_slice: pd.DataFrame) -> int:
    """
    Compute base_score (trend + momentum + volume + risk) from a DataFrame slice.

    Parameters
    ----------
    df_slice : pd.DataFrame
        OHLCV slice ending at the scoring date.

    Returns
    -------
    int — base_score (0 to 85)
    """
    feats_tech = compute_technical_features(df_slice)
    feats_vol = compute_volume_features(df_slice)
    feats_risk = compute_risk_features(df_slice)

    t = compute_trend_score(feats_tech)
    m = compute_momentum_score(feats_tech)
    v = compute_volume_score(feats_vol)
    r = compute_risk_score(feats_risk)
    return t + m + v + r


# ── Main backtest function ────────────────────────────────────────────────────

def run_backtest(
    tickers: list[str],
    start: str,
    end: str,
    top_n: int = 5,
    holding_days: int = 5,
    rebalance_every: int = 5,
    batch_delay: float = 0.2,
    verbose: bool = True,
) -> dict:
    """
    Run a walk-forward backtest over a list of tickers.

    Strategy
    --------
    - Every `rebalance_every` trading days, score all tickers using only
      data available up to that date.
    - Select top-N stocks by base_score.
    - Hold each for `holding_days` trading days, then record return.
    - Collect all trade returns and compute summary metrics.

    Parameters
    ----------
    tickers          : list[str] — e.g. ["2330.TW", "2454.TW", ...]
    start            : str — YYYY-MM-DD start of backtest window
    end              : str — YYYY-MM-DD end of backtest window
    top_n            : int — select top-N stocks per rebalance
    holding_days     : int — trading days to hold each position
    rebalance_every  : int — rebalance frequency in trading days
    batch_delay      : float — seconds between yfinance downloads
    verbose          : bool — print progress

    Returns
    -------
    dict with keys:
        trades         : list[TradeRecord]
        metrics        : dict from compute_metrics()
        report         : str — formatted report (format_metrics_report)
        holding_days   : int
        top_n          : int
        start          : str
        end            : str
        tickers_used   : list[str]
    """
    if verbose:
        print(f"[backtest] Fetching historical data for {len(tickers)} tickers ...")

    # ── 1. Fetch full history for all tickers ─────────────────────────────────
    history: dict[str, pd.DataFrame] = {}
    for i, ticker in enumerate(tickers):
        df = _fetch_full_history(ticker, start, end, batch_delay)
        if df is not None:
            history[ticker] = df
        else:
            if verbose:
                print(f"[backtest] SKIP: {ticker} (no data / delisted)")
        if i < len(tickers) - 1:
            time.sleep(batch_delay)

    if verbose:
        print(f"[backtest] Got data for {len(history)}/{len(tickers)} tickers")

    if not history:
        return _empty_result(start, end, top_n, holding_days, list(history.keys()))

    # ── 2. Build a common trading calendar ───────────────────────────────────
    # Use the union of all dates, then filter to [start, end]
    all_dates: set = set()
    for df in history.values():
        all_dates.update(df.index.tolist())

    start_dt = pd.Timestamp(start)
    end_dt = pd.Timestamp(end)
    trading_calendar = sorted(
        d for d in all_dates if start_dt <= d <= end_dt
    )

    if len(trading_calendar) < holding_days + 1:
        return _empty_result(start, end, top_n, holding_days, list(history.keys()))

    if verbose:
        print(
            f"[backtest] Trading calendar: {len(trading_calendar)} days "
            f"({trading_calendar[0].date()} → {trading_calendar[-1].date()})"
        )

    # ── 3. Walk-forward loop ──────────────────────────────────────────────────
    trades: list[TradeRecord] = []

    rebalance_indices = range(0, len(trading_calendar) - holding_days, rebalance_every)

    for idx in rebalance_indices:
        entry_ts = trading_calendar[idx]
        # Find exit date
        exit_idx = min(idx + holding_days, len(trading_calendar) - 1)
        exit_ts = trading_calendar[exit_idx]

        if exit_ts <= entry_ts:
            continue

        # Score all tickers using data up to entry_ts
        scores: list[tuple[str, int, float, float]] = []  # (ticker, base_score, entry_px, exit_px)

        for ticker, df in history.items():
            # Slice data up to and including entry_ts
            df_slice = df[df.index <= entry_ts]
            if len(df_slice) < 26:
                continue

            # Get entry price (close on entry_ts, or nearest available)
            entry_candidates = df[df.index <= entry_ts]
            if entry_candidates.empty:
                continue
            entry_price = float(entry_candidates["Close"].iloc[-1])

            # Get exit price (close on or after exit_ts)
            exit_candidates = df[df.index >= exit_ts]
            if exit_candidates.empty:
                # No data on/after exit_ts — use last available
                exit_candidates = df[df.index <= exit_ts]
                if exit_candidates.empty:
                    continue
            exit_price = float(exit_candidates["Close"].iloc[0] if len(exit_candidates) > 0 else entry_price)

            if entry_price <= 0 or exit_price <= 0:
                continue

            try:
                base_score = _compute_base_score(df_slice)
            except Exception:
                continue

            scores.append((ticker, base_score, entry_price, exit_price))

        if not scores:
            continue

        # Select top-N by base_score
        scores.sort(key=lambda x: x[1], reverse=True)
        selected = scores[:top_n]

        for ticker, base_score, entry_price, exit_price in selected:
            ret_pct = (exit_price - entry_price) / entry_price * 100.0
            trades.append(TradeRecord(
                ticker=ticker,
                entry_date=entry_ts.strftime("%Y-%m-%d"),
                exit_date=exit_ts.strftime("%Y-%m-%d"),
                entry_price=entry_price,
                exit_price=exit_price,
                return_pct=ret_pct,
            ))

    if verbose:
        print(f"[backtest] Total trades collected: {len(trades)}")

    # ── 4. Compute metrics ────────────────────────────────────────────────────
    returns = [t.return_pct for t in trades]
    metrics = compute_metrics(returns, holding_days=holding_days)

    report = format_metrics_report(
        metrics=metrics,
        holding_days=holding_days,
        universe_name=f"{len(tickers)} tickers",
        start=start,
        end=end,
        top_n=top_n,
    )

    return {
        "trades": trades,
        "metrics": metrics,
        "report": report,
        "holding_days": holding_days,
        "top_n": top_n,
        "start": start,
        "end": end,
        "tickers_used": list(history.keys()),
    }


def _empty_result(
    start: str,
    end: str,
    top_n: int,
    holding_days: int,
    tickers_used: list[str],
) -> dict:
    """Return an empty result dict when no trades could be generated."""
    metrics = compute_metrics([], holding_days=holding_days)
    report = format_metrics_report(
        metrics=metrics,
        holding_days=holding_days,
        start=start,
        end=end,
        top_n=top_n,
    )
    return {
        "trades": [],
        "metrics": metrics,
        "report": report,
        "holding_days": holding_days,
        "top_n": top_n,
        "start": start,
        "end": end,
        "tickers_used": tickers_used,
    }
