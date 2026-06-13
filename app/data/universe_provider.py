"""
app/data/universe_provider.py — Universe loader for Taiwan stock universes.

Loads ticker lists from data/universes/*.json.  Each entry must have:
    ticker  : str  — e.g. "2330.TW"
    code    : str  — numeric code only, e.g. "2330"
    name    : str  — Chinese company name
    sector  : str  — sector classification

Usage:
    from app.data.universe_provider import get_universe
    tickers = get_universe("tw0050")  # list of dicts
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TypedDict

from app.config import UNIVERSES_DIR


class TickerInfo(TypedDict):
    ticker: str
    code: str
    name: str
    sector: str


def get_universe(universe_name: str = "tw0050") -> list[TickerInfo]:
    """
    Load a universe JSON file and return a list of TickerInfo dicts.

    Parameters
    ----------
    universe_name : str
        Base name of the universe file (without .json extension).
        Defaults to "tw0050".

    Returns
    -------
    list[TickerInfo]
        At least 49 entries for tw0050 (50 minus any delisted).

    Raises
    ------
    FileNotFoundError
        If the universe file does not exist.
    ValueError
        If a required field is missing from any entry.
    """
    universe_path = UNIVERSES_DIR / f"{universe_name}.json"
    if not universe_path.exists():
        raise FileNotFoundError(f"Universe file not found: {universe_path}")

    with universe_path.open(encoding="utf-8") as fh:
        raw: list[dict] = json.load(fh)

    required_fields = {"ticker", "code", "name", "sector"}
    result: list[TickerInfo] = []
    for idx, entry in enumerate(raw):
        missing = required_fields - set(entry.keys())
        if missing:
            raise ValueError(
                f"Universe entry #{idx} is missing fields: {missing}. Entry: {entry}"
            )
        result.append(
            TickerInfo(
                ticker=str(entry["ticker"]),
                code=str(entry["code"]),
                name=str(entry["name"]),
                sector=str(entry["sector"]),
            )
        )

    return result


def get_tickers(universe_name: str = "tw0050") -> list[str]:
    """
    Convenience function: return only the ticker strings from a universe.

    Parameters
    ----------
    universe_name : str
        Base name of the universe file (without .json extension).

    Returns
    -------
    list[str]  — e.g. ["2330.TW", "2454.TW", ...]
    """
    return [entry["ticker"] for entry in get_universe(universe_name)]


def get_ticker_map(universe_name: str = "tw0050") -> dict[str, TickerInfo]:
    """
    Return a dict mapping ticker -> TickerInfo for fast lookup.

    Parameters
    ----------
    universe_name : str

    Returns
    -------
    dict[str, TickerInfo]
    """
    return {entry["ticker"]: entry for entry in get_universe(universe_name)}
