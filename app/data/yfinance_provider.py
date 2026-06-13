"""
app/data/yfinance_provider.py — OHLCV data fetcher using yfinance.

Rules:
- All tickers must use the .TW suffix (e.g., "2330.TW")
- 2888.TW is known-delisted; skip gracefully (return None, no exception)
- latest_data_date is derived from the DataFrame index, NOT date.today()
- Caches results to data/cache/ as Parquet files keyed by (ticker, fetch_date)

Usage:
    from app.data.yfinance_provider import fetch_ohlcv
    result = fetch_ohlcv("2330.TW")
    if result is not None:
        df = result["df"]
        latest_date = result["latest_data_date"]
"""

from __future__ import annotations

import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, TypedDict

import pandas as pd
import yfinance as yf

from app.config import CACHE_DIR, DELISTED_TICKERS, YFINANCE_HISTORY_DAYS


class OHLCVResult(TypedDict):
    ticker: str
    df: pd.DataFrame              # OHLCV DataFrame, index=Date (no tz), no NaN in Close
    latest_data_date: str         # YYYY-MM-DD derived from df.index[-1]


def _cache_path(ticker: str, fetch_date: str) -> Path:
    """Parquet cache path for a (ticker, fetch_date) pair."""
    safe = ticker.replace(".", "_")
    return CACHE_DIR / f"{safe}_{fetch_date}.parquet"


def _load_from_cache(ticker: str, fetch_date: str) -> Optional[pd.DataFrame]:
    path = _cache_path(ticker, fetch_date)
    if path.exists():
        try:
            return pd.read_parquet(path)
        except Exception:
            path.unlink(missing_ok=True)
    return None


def _save_to_cache(df: pd.DataFrame, ticker: str, fetch_date: str) -> None:
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        df.to_parquet(_cache_path(ticker, fetch_date))
    except Exception:
        pass  # cache write failure is non-fatal


def fetch_ohlcv(
    ticker: str,
    days: int = YFINANCE_HISTORY_DAYS,
    fetch_date: Optional[str] = None,
    retries: int = 3,
    retry_delay: float = 2.0,
) -> Optional[OHLCVResult]:
    """
    Fetch OHLCV data for a single Taiwan stock ticker.

    Parameters
    ----------
    ticker     : str   — must use .TW suffix, e.g. "2330.TW"
    days       : int   — calendar days of history to fetch
    fetch_date : str   — YYYY-MM-DD cache key (default: today's date string)
    retries    : int   — retry attempts on transient errors
    retry_delay: float — seconds between retries

    Returns
    -------
    OHLCVResult dict or None if:
    - ticker is in DELISTED_TICKERS
    - yfinance returns no data after all retries
    - resulting DataFrame has fewer than 26 rows (not enough for MACD)

    Notes
    -----
    latest_data_date is always derived from df.index[-1], NEVER from date.today().
    """
    # Gracefully skip known-delisted tickers
    if ticker in DELISTED_TICKERS:
        return None

    if fetch_date is None:
        fetch_date = datetime.today().strftime("%Y-%m-%d")

    # Try cache first
    cached = _load_from_cache(ticker, fetch_date)
    if cached is not None and not cached.empty and len(cached) >= 26:
        latest_date = cached.index[-1]
        if hasattr(latest_date, "strftime"):
            latest_data_date = latest_date.strftime("%Y-%m-%d")
        else:
            latest_data_date = str(latest_date)[:10]
        return OHLCVResult(
            ticker=ticker,
            df=cached,
            latest_data_date=latest_data_date,
        )

    end_dt = datetime.today()
    start_dt = end_dt - timedelta(days=days + 14)  # buffer for weekends/holidays

    last_err: Optional[Exception] = None
    for attempt in range(1, retries + 1):
        try:
            raw = yf.download(
                ticker,
                start=start_dt.strftime("%Y-%m-%d"),
                end=end_dt.strftime("%Y-%m-%d"),
                auto_adjust=True,
                progress=False,
            )
            if raw is None or raw.empty:
                return None

            # Normalise columns (yfinance may return MultiIndex)
            if isinstance(raw.columns, pd.MultiIndex):
                raw.columns = raw.columns.get_level_values(0)

            needed = [c for c in ["Open", "High", "Low", "Close", "Volume"] if c in raw.columns]
            df = raw[needed].copy()
            df.index = pd.to_datetime(df.index).tz_localize(None)
            df.index.name = "Date"
            df = df.dropna(subset=["Close"])
            df = df.tail(days)

            if df.empty or len(df) < 26:
                return None

            # Derive latest_data_date from index — NEVER use date.today()
            latest_dt = df.index[-1]
            if hasattr(latest_dt, "strftime"):
                latest_data_date = latest_dt.strftime("%Y-%m-%d")
            else:
                latest_data_date = str(latest_dt)[:10]

            _save_to_cache(df, ticker, fetch_date)
            return OHLCVResult(
                ticker=ticker,
                df=df,
                latest_data_date=latest_data_date,
            )

        except Exception as exc:
            last_err = exc
            if attempt < retries:
                time.sleep(retry_delay)

    print(
        f"[yfinance_provider] WARNING: failed to fetch {ticker} "
        f"after {retries} attempts: {last_err}"
    )
    return None


def fetch_universe_ohlcv(
    tickers: list[str],
    days: int = YFINANCE_HISTORY_DAYS,
    fetch_date: Optional[str] = None,
    batch_delay: float = 0.3,
) -> dict[str, OHLCVResult]:
    """
    Fetch OHLCV data for a list of tickers.

    Skips tickers in DELISTED_TICKERS and any that return None from fetch_ohlcv.

    Parameters
    ----------
    tickers     : list[str]
    days        : int
    fetch_date  : str — YYYY-MM-DD (default: today)
    batch_delay : float — seconds between requests

    Returns
    -------
    dict[str, OHLCVResult] — only successfully fetched tickers are included
    """
    if fetch_date is None:
        fetch_date = datetime.today().strftime("%Y-%m-%d")

    results: dict[str, OHLCVResult] = {}
    for i, ticker in enumerate(tickers):
        result = fetch_ohlcv(ticker, days=days, fetch_date=fetch_date)
        if result is not None:
            results[ticker] = result
        else:
            print(f"[yfinance_provider] SKIP: {ticker}")
        if i < len(tickers) - 1:
            time.sleep(batch_delay)

    skipped = len(tickers) - len(results)
    print(
        f"[yfinance_provider] Fetched {len(results)}/{len(tickers)} tickers "
        f"({skipped} skipped)"
    )
    return results
