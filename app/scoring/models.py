"""
app/scoring/models.py — StockRadarResult dataclass (V2 data model).

This is the central data model for all scoring, formatting, and backtesting.
All Optional[float] fields default to None — never use NaN.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class StockRadarResult:
    """Complete V2 radar analysis result for one stock."""

    # ── Identity ──────────────────────────────────────────────────────────────
    ticker: str
    code: str
    name: str
    data_date: str                          # YYYY-MM-DD from latest_data_date

    # ── Price ─────────────────────────────────────────────────────────────────
    latest_close: float
    price_change_1d_pct: float              # % change vs previous close
    price_change_5d_pct: float              # % change over 5 trading days

    # ── Ranking & Direction ───────────────────────────────────────────────────
    radar_score: int                        # 0–100 (clamped)
    rank_in_universe: int                   # 1-based rank (1 = highest radar_score)
    universe_size: int
    direction: str                          # "bullish" / "neutral" / "bearish"
    confidence: str                         # "高" / "中" / "低"

    # ── Sub-scores ────────────────────────────────────────────────────────────
    trend_score: int                        # 0–30
    momentum_score: int                     # 0–20
    volume_score: int                       # 0–20
    risk_score: int                         # 0–15
    market_score: int                       # 0–10
    chip_score: Optional[int] = None        # Reserved; always None for now

    # ── Indicators (display) ──────────────────────────────────────────────────
    ma5: float = 0.0
    ma20: float = 0.0
    ma60: Optional[float] = None
    rsi14: float = 0.0
    macd_hist: float = 0.0
    macd_hist_delta: float = 0.0
    volume_ratio: float = 1.0
    atr14: float = 0.0
    atr_pct: float = 0.0
    support_20d: float = 0.0
    resistance_20d: float = 0.0

    # ── Explanations ──────────────────────────────────────────────────────────
    positive_reasons: List[str] = field(default_factory=list)
    negative_reasons: List[str] = field(default_factory=list)
    risk_notes: List[str] = field(default_factory=list)
    invalidation_conditions: List[str] = field(default_factory=list)

    # ── Backtesting (all Optional — None until explicitly invoked) ────────────
    historical_win_rate_5d: Optional[float] = None
    historical_avg_return_5d: Optional[float] = None
    historical_win_rate_10d: Optional[float] = None
    historical_avg_return_10d: Optional[float] = None

    # ── Derived property ──────────────────────────────────────────────────────
    @property
    def base_score(self) -> int:
        """
        Selection gate score = trend + momentum + volume + risk.

        IMPORTANT (ICR-1): Stock selection into strong_watchlist uses base_score,
        NOT radar_score.  market_score is excluded to prevent market context
        from pushing weak individual stocks into the watchlist.
        """
        return self.trend_score + self.momentum_score + self.volume_score + self.risk_score
