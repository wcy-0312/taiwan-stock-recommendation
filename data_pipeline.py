"""
ART-001: Data Pipeline — WS-1
Fetches 60 days of OHLCV data for Taiwan stock tickers using yfinance.
Caches daily results to avoid redundant API calls.
"""

import json
import os
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional

import pandas as pd
import yfinance as yf

# ── Cache configuration ──────────────────────────────────────────────────────
_CACHE_DIR = Path(__file__).parent / ".cache"
_CACHE_DIR.mkdir(exist_ok=True)

# Default 0050 ETF component universe (as of mid-2025; update periodically)
TAIWAN_0050_TICKERS = [
    "2330.TW",  # TSMC
    "2454.TW",  # MediaTek
    "2317.TW",  # Hon Hai / Foxconn
    "2308.TW",  # Delta Electronics
    "2882.TW",  # Cathay Financial
    "2881.TW",  # Fubon Financial
    "2303.TW",  # United Microelectronics
    "1301.TW",  # Formosa Plastics
    "1303.TW",  # Nan Ya Plastics
    "2412.TW",  # Chunghwa Telecom
    "2002.TW",  # China Steel
    "1326.TW",  # Formosa Chemicals
    "2886.TW",  # Mega Financial
    "2884.TW",  # E. Sun Financial
    "3711.TW",  # ASE Technology
    "2891.TW",  # CTBC Financial
    "2892.TW",  # First Financial
    "5880.TW",  # Taiwan Cooperative Financial
    "2885.TW",  # Yuanta Financial
    "2880.TW",  # Hua Nan Financial
    "2883.TW",  # China Development Financial
    "2887.TW",  # Taishin Financial
    "2888.TW",  # Shin Kong Financial
    "2890.TW",  # SinoPac Financial
    "2801.TW",  # Chang Hwa Commercial Bank
    "1402.TW",  # Far Eastern New Century
    "2207.TW",  # Hotai Motor
    "2382.TW",  # Quanta Computer
    "2395.TW",  # Advantech
    "4938.TW",  # Pegatron
    "2357.TW",  # ASUS
    "2379.TW",  # Realtek
    "3034.TW",  # Novatek
    "2327.TW",  # Yageo
    "2301.TW",  # Lite-On Technology
    "6505.TW",  # Formosa Petrochemical
    "2353.TW",  # Acer
    "2352.TW",  # Compal Electronics
    "2356.TW",  # Inventec
    "3008.TW",  # Largan Precision
    "2376.TW",  # Gigabyte Technology
    "2385.TW",  # Cheng Uei Precision Industry
    "2408.TW",  # Nanya Technology
    "3006.TW",  # Leofoo Development
    "2474.TW",  # Can-Fite BioPharma (placeholder)
    "2603.TW",  # Evergreen Marine
    "2615.TW",  # Wan Hai Lines
    "2609.TW",  # Yang Ming Marine
    "2610.TW",  # China Airlines
    "2618.TW",  # Eva Air
]


def _cache_path(ticker: str, fetch_date: str) -> Path:
    """Return the cache file path for a ticker on a given date."""
    safe = ticker.replace(".", "_")
    return _CACHE_DIR / f"{safe}_{fetch_date}.parquet"


def _load_from_cache(ticker: str, fetch_date: str) -> Optional[pd.DataFrame]:
    """Load cached DataFrame if available."""
    path = _cache_path(ticker, fetch_date)
    if path.exists():
        try:
            return pd.read_parquet(path)
        except Exception:
            path.unlink(missing_ok=True)
    return None


def _save_to_cache(df: pd.DataFrame, ticker: str, fetch_date: str) -> None:
    """Persist DataFrame to cache."""
    try:
        df.to_parquet(_cache_path(ticker, fetch_date))
    except Exception:
        pass  # cache write failure is non-fatal


def fetch_ticker(
    ticker: str,
    days: int = 60,
    fetch_date: Optional[str] = None,
    retries: int = 3,
    retry_delay: float = 2.0,
) -> Optional[pd.DataFrame]:
    """
    Fetch OHLCV data for a single ticker.

    Parameters
    ----------
    ticker      : str   — e.g. '2330.TW'
    days        : int   — calendar days of history to fetch (default 60)
    fetch_date  : str   — YYYY-MM-DD cache key (default today)
    retries     : int   — number of retry attempts on transient errors
    retry_delay : float — seconds to wait between retries

    Returns
    -------
    pd.DataFrame with columns [Open, High, Low, Close, Volume] indexed by Date,
    or None if data could not be fetched.
    """
    if fetch_date is None:
        fetch_date = date.today().isoformat()

    # Try cache first
    cached = _load_from_cache(ticker, fetch_date)
    if cached is not None and not cached.empty:
        return cached

    end = datetime.today()
    start = end - timedelta(days=days + 10)  # buffer for weekends/holidays

    last_err = None
    for attempt in range(1, retries + 1):
        try:
            raw = yf.download(
                ticker,
                start=start.strftime("%Y-%m-%d"),
                end=end.strftime("%Y-%m-%d"),
                auto_adjust=True,
                progress=False,
            )
            if raw is None or raw.empty:
                return None

            # Normalise column names: yfinance may return MultiIndex
            if isinstance(raw.columns, pd.MultiIndex):
                raw.columns = raw.columns.get_level_values(0)

            # Keep only standard OHLCV columns
            needed = [c for c in ["Open", "High", "Low", "Close", "Volume"] if c in raw.columns]
            df = raw[needed].copy()
            df.index = pd.to_datetime(df.index).tz_localize(None)
            df.index.name = "Date"
            df = df.dropna(subset=["Close"])
            df = df.tail(days)  # keep at most `days` rows

            if df.empty:
                return None

            _save_to_cache(df, ticker, fetch_date)
            return df

        except Exception as exc:
            last_err = exc
            if attempt < retries:
                time.sleep(retry_delay)

    print(f"[data_pipeline] WARNING: failed to fetch {ticker} after {retries} attempts: {last_err}")
    return None


def fetch_universe(
    tickers: Optional[list] = None,
    days: int = 60,
    fetch_date: Optional[str] = None,
    batch_delay: float = 0.3,
) -> dict:
    """
    Fetch OHLCV data for a list of tickers.

    Parameters
    ----------
    tickers     : list  — ticker symbols (defaults to TAIWAN_0050_TICKERS)
    days        : int   — history window in calendar days
    fetch_date  : str   — YYYY-MM-DD cache key (default today)
    batch_delay : float — seconds between individual ticker fetches

    Returns
    -------
    dict of {ticker: pd.DataFrame}; failed tickers are omitted.
    """
    if tickers is None:
        tickers = TAIWAN_0050_TICKERS

    if fetch_date is None:
        fetch_date = date.today().isoformat()

    results = {}
    for i, ticker in enumerate(tickers):
        df = fetch_ticker(ticker, days=days, fetch_date=fetch_date)
        if df is not None and not df.empty:
            results[ticker] = df
        else:
            print(f"[data_pipeline] SKIP: {ticker} — no data returned")
        if i < len(tickers) - 1:
            time.sleep(batch_delay)

    print(
        f"[data_pipeline] Fetched {len(results)}/{len(tickers)} tickers "
        f"({len(tickers) - len(results)} skipped)"
    )
    return results


# ── Quick smoke test ──────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("=== data_pipeline smoke test ===")
    test_tickers = ["2330.TW", "2454.TW", "2317.TW"]
    data = fetch_universe(tickers=test_tickers, days=60)
    for ticker, df in data.items():
        print(f"\n{ticker}: {len(df)} rows")
        print(df.tail(3).to_string())
    print("\n[PASS] data_pipeline smoke test complete")
