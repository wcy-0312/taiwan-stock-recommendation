"""
app/recommendation/selector.py — Stock selection logic for V2 radar system.

Selection uses base_score (trend+momentum+volume+risk), NOT radar_score.
This is enforced per ICR-1 / DL-9: market context cannot push weak stocks in.

Selection categories:
    strong_watchlist : base_score >= 70, sorted desc, max 5, broadcast top 3
    weakness_alerts  : base_score <= 35, sorted asc (worst first), max 5, broadcast top 2
    turning_points   : MACD crossed up/down, reclaimed/broke MA20, high-volume breakout
"""

from __future__ import annotations

from enum import Enum

from app.scoring.models import StockRadarResult
from app.config import (
    BASE_SCORE_STRONG_THRESHOLD,
    BASE_SCORE_WEAK_THRESHOLD,
    STRONG_WATCHLIST_MAX,
    STRONG_WATCHLIST_BROADCAST_TOP,
    WEAKNESS_ALERTS_MAX,
    WEAKNESS_ALERTS_BROADCAST_TOP,
)


class StockCategory(str, Enum):
    STRONG_CONTINUE = "強勢延續"     # High score, stable trend, normal volume, low risk
    JUST_TURNED_STRONG = "剛轉強"    # MACD flipped positive, reclaimed MA20, volume up
    OVERHEATED = "過熱勿追"          # High score but RSI > 75 or near resistance
    WEAKNESS_ALERT = "轉弱警示"      # Low base_score, broke MA20, MACD negative
    WATCHING = "觀望整理"            # Mid-range score, mixed signals


def categorize_stock(result) -> StockCategory:
    """
    Categorize a StockRadarResult into one of 5 product-facing categories.

    Parameters
    ----------
    result : StockRadarResult

    Returns
    -------
    StockCategory
    """
    from app.config import BASE_SCORE_STRONG_THRESHOLD, BASE_SCORE_WEAK_THRESHOLD

    bs = result.base_score
    rsi = result.rsi14
    macd = result.macd_hist
    macd_delta = result.macd_hist_delta

    # Weakness alert: low base score
    if bs <= BASE_SCORE_WEAK_THRESHOLD:
        return StockCategory.WEAKNESS_ALERT

    # Strong stocks — check sub-categories
    if bs >= BASE_SCORE_STRONG_THRESHOLD:
        # Overheated: RSI > 75 or near resistance
        if rsi > 75 or (result.resistance_20d > 0 and result.latest_close / result.resistance_20d > 0.97):
            return StockCategory.OVERHEATED
        # Just turned strong: MACD just flipped positive (delta > 0 and macd was near 0)
        if macd > 0 and macd_delta > 0 and abs(macd) < 1.0:
            return StockCategory.JUST_TURNED_STRONG
        # Default strong
        return StockCategory.STRONG_CONTINUE

    # Watching: mid range
    return StockCategory.WATCHING


def categorize_results(results: list) -> dict:
    """
    Group a list of StockRadarResult by StockCategory.

    Returns dict mapping StockCategory -> list of results.
    """
    grouped = {cat: [] for cat in StockCategory}
    for r in results:
        cat = categorize_stock(r)
        grouped[cat].append(r)
    return grouped


def select_strong_watchlist(
    results: list[StockRadarResult],
    max_stocks: int = STRONG_WATCHLIST_MAX,
) -> list[StockRadarResult]:
    """
    Select strong watchlist stocks.

    Criteria: base_score >= BASE_SCORE_STRONG_THRESHOLD (70)
    Sorted: descending by radar_score (display ranking)
    Capped: max_stocks entries

    ICR-1: Uses base_score for threshold, NOT radar_score.
    """
    candidates = [
        r for r in results
        if r.base_score >= BASE_SCORE_STRONG_THRESHOLD
    ]
    candidates.sort(key=lambda r: r.radar_score, reverse=True)
    return candidates[:max_stocks]


def select_weakness_alerts(
    results: list[StockRadarResult],
    max_stocks: int = WEAKNESS_ALERTS_MAX,
) -> list[StockRadarResult]:
    """
    Select weakness alert stocks.

    Criteria: base_score <= BASE_SCORE_WEAK_THRESHOLD (35)
    Sorted: ascending by radar_score (weakest first)
    Capped: max_stocks entries

    ICR-1: Uses base_score for threshold, NOT radar_score.
    """
    candidates = [
        r for r in results
        if r.base_score <= BASE_SCORE_WEAK_THRESHOLD
    ]
    candidates.sort(key=lambda r: r.radar_score)  # ascending: weakest first
    return candidates[:max_stocks]


def select_turning_points(results: list[StockRadarResult]) -> list[StockRadarResult]:
    """
    Select turning point stocks.

    Criteria (any one of):
        - MACD histogram flipped positive (macd_crossed_up)
        - MACD histogram flipped negative (macd_crossed_down)
        - Close reclaimed MA20 (close_above_ma20 changed)
        - High-volume breakout above 20-day high (volume_expansion + near_resistance reversal)

    Note: The StockRadarResult does not directly store macd_crossed_up/down
    as fields — we check positive_reasons / negative_reasons for turning signals.
    """
    turning: list[StockRadarResult] = []
    for r in results:
        is_turning = False
        # Check positive reasons for turning signals
        for reason in r.positive_reasons:
            if "翻正" in reason or "轉折向上" in reason:
                is_turning = True
                break
        # Check negative reasons for turning signals
        if not is_turning:
            for reason in r.negative_reasons:
                if "翻負" in reason or "轉折向下" in reason:
                    is_turning = True
                    break
        if is_turning:
            turning.append(r)

    # Sort by abs(radar_score - 50) descending: most decisive first
    turning.sort(key=lambda r: abs(r.radar_score - 50), reverse=True)
    return turning


class SelectionResult:
    """Container for all selection outputs from one analysis run."""

    def __init__(
        self,
        all_results: list[StockRadarResult],
        strong_watchlist: list[StockRadarResult],
        weakness_alerts: list[StockRadarResult],
        turning_points: list[StockRadarResult],
        broadcast_strong: list[StockRadarResult],
        broadcast_weak: list[StockRadarResult],
    ):
        self.all_results = all_results
        self.strong_watchlist = strong_watchlist
        self.weakness_alerts = weakness_alerts
        self.turning_points = turning_points
        self.broadcast_strong = broadcast_strong
        self.broadcast_weak = broadcast_weak

    @property
    def has_strong(self) -> bool:
        return len(self.broadcast_strong) > 0

    @property
    def has_weak(self) -> bool:
        return len(self.broadcast_weak) > 0


def run_selection(results: list[StockRadarResult]) -> SelectionResult:
    """
    Run all three selection passes and return a SelectionResult.

    This is the primary entry point for the recommendation pipeline.

    Parameters
    ----------
    results : list[StockRadarResult]
        All stocks that were successfully scored this run.

    Returns
    -------
    SelectionResult
    """
    strong = select_strong_watchlist(results)
    weak = select_weakness_alerts(results)
    turning = select_turning_points(results)

    broadcast_strong = strong[:STRONG_WATCHLIST_BROADCAST_TOP]
    broadcast_weak = weak[:WEAKNESS_ALERTS_BROADCAST_TOP]

    return SelectionResult(
        all_results=results,
        strong_watchlist=strong,
        weakness_alerts=weak,
        turning_points=turning,
        broadcast_strong=broadcast_strong,
        broadcast_weak=broadcast_weak,
    )
