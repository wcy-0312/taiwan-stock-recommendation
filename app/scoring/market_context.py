"""
app/scoring/market_context.py — Universe-level market context scorer.

Computes a market_score (0–10) based on aggregate signals across the universe.
This score represents the overall market environment and is added AFTER
individual stock selection.

CRITICAL (ICR-1 / DL-9):
    market_score is NEVER used for stock selection.
    Selection gates use base_score (trend+momentum+volume+risk) only.
    market_score only affects the final radar_score for display and ranking.
"""

from __future__ import annotations

from typing import Optional


def compute_market_score(
    base_scores: list[int],
    bull_threshold: int = 70,
) -> int:
    """
    Compute a universe-level market context score (0–10).

    Uses the distribution of base_scores across all stocks to assess
    whether the overall market environment is bullish, neutral, or bearish.

    Parameters
    ----------
    base_scores  : list[int]
        base_score values for all stocks in the universe that were scored.
    bull_threshold : int
        base_score threshold above which a stock is considered "bullish" (default 70).

    Returns
    -------
    int — market_score in [0, 10]
    """
    if not base_scores:
        return 5  # neutral default when no data

    n = len(base_scores)
    bullish_count = sum(1 for s in base_scores if s >= bull_threshold)
    bullish_ratio = bullish_count / n

    # Average score of all stocks
    avg_score = sum(base_scores) / n

    # Score bands:
    # 8–10: Very bullish market (>= 60% stocks bullish, avg >= 65)
    # 6–7:  Bullish market     (>= 40% stocks bullish, avg >= 55)
    # 4–5:  Neutral            (20–40% stocks bullish)
    # 2–3:  Mildly bearish     (< 20% stocks bullish, avg < 50)
    # 0–1:  Bearish market     (< 10% stocks bullish, avg < 40)

    if bullish_ratio >= 0.60 and avg_score >= 65:
        market_score = 9
    elif bullish_ratio >= 0.50 and avg_score >= 60:
        market_score = 8
    elif bullish_ratio >= 0.40 and avg_score >= 55:
        market_score = 7
    elif bullish_ratio >= 0.30 and avg_score >= 50:
        market_score = 6
    elif bullish_ratio >= 0.20:
        market_score = 5
    elif bullish_ratio >= 0.15 and avg_score >= 45:
        market_score = 4
    elif bullish_ratio >= 0.10:
        market_score = 3
    elif avg_score >= 40:
        market_score = 2
    else:
        market_score = 1

    return max(0, min(10, market_score))


def compute_market_context_stats(base_scores: list[int]) -> dict:
    """
    Compute descriptive stats about the universe for display purposes.

    Returns
    -------
    dict with keys:
        bullish_count  : int
        bullish_ratio  : float  (0.0–1.0)
        avg_base_score : float
        universe_size  : int
        market_score   : int    (0–10)
    """
    if not base_scores:
        return {
            "bullish_count": 0,
            "bullish_ratio": 0.0,
            "avg_base_score": 0.0,
            "universe_size": 0,
            "market_score": 5,
        }

    n = len(base_scores)
    bullish_count = sum(1 for s in base_scores if s >= 70)
    bullish_ratio = bullish_count / n
    avg_base_score = sum(base_scores) / n
    market_score = compute_market_score(base_scores)

    return {
        "bullish_count": bullish_count,
        "bullish_ratio": round(bullish_ratio, 3),
        "avg_base_score": round(avg_base_score, 1),
        "universe_size": n,
        "market_score": market_score,
    }
