"""
app/cache/latest_cache.py — Latest analysis cache helpers.

Scans data/cache/analysis_*.json files, picks the most recent one regardless
of whether it matches today's date.  This means the cache always returns
data even on weekends and public holidays (台股六日不交易).

Public API
----------
load_latest_analysis_cache() -> Optional[dict]
    Return the full cache dict (keys: results, market_stats) or None.

get_latest_analysis_date() -> str
    Return the date string from the most recent cache file ("YYYY-MM-DD"),
    or "—" if no cache exists.

find_stock_in_latest_cache(ticker: str) -> Optional[dict]
    Return the raw result dict for the given ticker from the latest cache,
    or None if not found.

list_latest_results() -> list[dict]
    Return all result dicts from the latest cache, or [] if no cache.

get_latest_market_stats() -> dict
    Return the market_stats dict from the latest cache, or {}.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional

from app.config import CACHE_DIR

logger = logging.getLogger(__name__)

# ── Internal helpers ──────────────────────────────────────────────────────────

def _iter_cache_files():
    """Yield cache file paths sorted newest-first."""
    if not CACHE_DIR.exists():
        return
    yield from sorted(CACHE_DIR.glob("analysis_*.json"), reverse=True)


def _read_cache_file(path: Path) -> Optional[dict]:
    """Parse a single cache file; returns None on error."""
    try:
        with path.open(encoding="utf-8") as fh:
            return json.load(fh)
    except Exception as exc:
        logger.warning("latest_cache: failed to read %s — %s", path, exc)
        return None


def _latest_cache_file() -> Optional[Path]:
    """Return the path of the most recent cache file, or None."""
    for path in _iter_cache_files():
        return path
    return None


# ── Public API ────────────────────────────────────────────────────────────────

def load_latest_analysis_cache() -> Optional[dict]:
    """
    Load the most recent analysis cache, regardless of whether it is from today.

    Returns
    -------
    dict with keys 'results' (list) and 'market_stats' (dict), or None.
    """
    path = _latest_cache_file()
    if path is None:
        logger.debug("latest_cache: no cache files found in %s", CACHE_DIR)
        return None
    data = _read_cache_file(path)
    if data is None:
        return None
    logger.debug("latest_cache: loaded %s", path.name)
    return data


def get_latest_analysis_date() -> str:
    """
    Return the date string from the most recent cache file ("YYYY-MM-DD"),
    or "—" if no cache exists.
    """
    path = _latest_cache_file()
    if path is None:
        return "—"
    # Filename format: analysis_YYYY-MM-DD.json
    stem = path.stem  # e.g. "analysis_2026-06-13"
    return stem.replace("analysis_", "")


def find_stock_in_latest_cache(ticker: str) -> Optional[dict]:
    """
    Return the raw result dict for `ticker` from the latest cache file.

    Searches up to the 3 most-recent cache files (in case the stock is
    missing from the very latest run due to a transient error).

    Parameters
    ----------
    ticker : str — ticker with or without .TW suffix (e.g. "2330" or "2330.TW")

    Returns
    -------
    dict or None
    """
    # Normalise to uppercase with .TW suffix
    t = ticker.strip().upper()
    if not t.endswith(".TW"):
        t = t + ".TW"

    files = list(_iter_cache_files())
    for path in files[:3]:
        data = _read_cache_file(path)
        if data is None:
            continue
        for r in data.get("results", []):
            if r.get("ticker", "").upper() == t:
                return r
    return None


def list_latest_results() -> list[dict]:
    """
    Return all result dicts from the most recent cache file.

    Returns
    -------
    list[dict] — may be empty if no cache exists.
    """
    data = load_latest_analysis_cache()
    if data is None:
        return []
    return data.get("results", [])


def get_latest_market_stats() -> dict:
    """
    Return the market_stats dict from the most recent cache file.

    Returns
    -------
    dict — may be empty if no cache exists.
    """
    data = load_latest_analysis_cache()
    if data is None:
        return {}
    return data.get("market_stats", {})
