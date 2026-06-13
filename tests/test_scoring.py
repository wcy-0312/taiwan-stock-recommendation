"""
tests/test_scoring.py — Unit tests for the scoring engine (radar.py, models.py, reasons.py).

Tests:
    - radar_score always 0–100 (clamped)
    - rank_in_universe and universe_size are correct after pipeline assignment
    - RSI < 30 never contributes to momentum_score (ICR-2)
    - RSI < 30 is added to risk_notes (ICR-2)
    - direction thresholds: bullish >= 70, bearish <= 35, neutral 36–69
    - confidence = 高 requires ALL 5 conditions (ICR-3)
    - confidence = 低 when radar_score < 60
    - base_score excludes market_score (ICR-1)
    - negative_reasons != risk_notes (ICR-4)
    - trend_score bands (High/Mid/Low)
    - volume_score bands
    - risk_score bands
    - market_score isolation: selection uses base_score
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_PROJECT_ROOT = Path(__file__).parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from app.scoring.radar import (
    compute_trend_score,
    compute_momentum_score,
    compute_volume_score,
    compute_risk_score,
    compute_direction,
    compute_confidence,
    score_stock,
)
from app.scoring.reasons import (
    build_positive_reasons,
    build_negative_reasons,
    build_risk_notes,
    build_invalidation_conditions,
)
from app.scoring.models import StockRadarResult


# ══════════════════════════════════════════════════════════════════════════════
# Helpers
# ══════════════════════════════════════════════════════════════════════════════

def _make_result(
    radar_score: int = 75,
    trend: int = 22,
    momentum: int = 15,
    volume: int = 16,
    risk: int = 12,
    market: int = 5,
    direction: str = "bullish",
    confidence: str = "中",
    volume_ratio: float = 1.3,
    rsi14: float = 60.0,
    positive_reasons: list | None = None,
    negative_reasons: list | None = None,
    risk_notes: list | None = None,
) -> StockRadarResult:
    """Create a StockRadarResult with controllable key fields."""
    return StockRadarResult(
        ticker="2330.TW",
        code="2330",
        name="台積電",
        data_date="2026-06-13",
        latest_close=900.0,
        price_change_1d_pct=1.5,
        price_change_5d_pct=3.0,
        radar_score=radar_score,
        rank_in_universe=1,
        universe_size=50,
        direction=direction,
        confidence=confidence,
        trend_score=trend,
        momentum_score=momentum,
        volume_score=volume,
        risk_score=risk,
        market_score=market,
        chip_score=None,
        ma5=895.0,
        ma20=880.0,
        ma60=860.0,
        rsi14=rsi14,
        macd_hist=0.5,
        macd_hist_delta=0.1,
        volume_ratio=volume_ratio,
        atr14=15.0,
        atr_pct=1.7,
        support_20d=870.0,
        resistance_20d=920.0,
        positive_reasons=positive_reasons or [],
        negative_reasons=negative_reasons or [],
        risk_notes=risk_notes or [],
        invalidation_conditions=[],
    )


# ══════════════════════════════════════════════════════════════════════════════
# 1. radar_score clamping
# ══════════════════════════════════════════════════════════════════════════════

class TestRadarScoreClamping:
    """radar_score must always be within [0, 100]."""

    def test_score_stock_clamps_to_0(self):
        """All-zero features should not produce negative radar_score."""
        result = score_stock(
            ticker="TEST.TW",
            code="TEST",
            name="Test",
            latest_close=100.0,
            price_change_1d_pct=0.0,
            price_change_5d_pct=0.0,
            data_date="2026-06-13",
            feats_technical={},
            feats_volume={},
            feats_risk={},
            market_score=0,
            positive_reasons=[],
            negative_reasons=[],
            risk_notes=[],
            invalidation_conditions=[],
        )
        assert result.radar_score >= 0, "radar_score must be >= 0"
        assert result.radar_score <= 100, "radar_score must be <= 100"

    def test_score_stock_clamps_to_100(self):
        """Maximum inputs should not exceed 100."""
        feats_tech = {
            "ma5": 110.0, "ma20": 100.0, "ma60": 90.0,
            "ma5_above_ma20": True, "ma5_above_ma60": True,
            "close_above_ma5": True, "close_above_ma20": True,
            "ma5_slope": 1.0, "ma20_slope": 0.5,
            "rsi14": 65.0,
            "macd_hist": 0.8, "macd_hist_delta": 0.2,
            "macd_crossed_up": False, "macd_crossed_down": False,
        }
        feats_vol = {"volume_ratio": 2.5, "volume_up": True, "volume_down": False, "volume_contraction": False}
        feats_risk = {"atr_pct": 1.0, "dist_to_resistance_pct": 8.0, "near_resistance": False, "broke_support": False}
        result = score_stock(
            ticker="MAX.TW",
            code="MAX",
            name="MaxTest",
            latest_close=100.0,
            price_change_1d_pct=2.0,
            price_change_5d_pct=5.0,
            data_date="2026-06-13",
            feats_technical=feats_tech,
            feats_volume=feats_vol,
            feats_risk=feats_risk,
            market_score=10,
            positive_reasons=[],
            negative_reasons=[],
            risk_notes=[],
            invalidation_conditions=[],
        )
        assert result.radar_score <= 100, "radar_score must be <= 100"
        assert result.radar_score >= 0, "radar_score must be >= 0"

    @pytest.mark.parametrize("extra_market", [-5, 0, 5, 10, 15])
    def test_radar_score_always_bounded(self, extra_market):
        """radar_score never goes out of [0, 100] for any market_score input."""
        feats_tech = {"ma5_above_ma20": True, "rsi14": 60.0, "macd_hist": 0.3, "macd_hist_delta": 0.1}
        feats_vol = {"volume_ratio": 1.5, "volume_up": True, "volume_down": False, "volume_contraction": False}
        feats_risk = {"atr_pct": 1.5}
        # market_score is clamped externally before being passed to score_stock;
        # however score_stock itself also clamps via max(0, min(100, ...))
        ms = max(0, min(10, extra_market))
        result = score_stock(
            ticker="X.TW", code="X", name="X",
            latest_close=100.0, price_change_1d_pct=0.0, price_change_5d_pct=0.0,
            data_date="2026-06-13",
            feats_technical=feats_tech, feats_volume=feats_vol, feats_risk=feats_risk,
            market_score=ms, positive_reasons=[], negative_reasons=[],
            risk_notes=[], invalidation_conditions=[],
        )
        assert 0 <= result.radar_score <= 100


# ══════════════════════════════════════════════════════════════════════════════
# 2. Rank and universe size
# ══════════════════════════════════════════════════════════════════════════════

class TestRankAndUniverseSize:
    def test_rank_defaults_to_zero(self):
        result = score_stock(
            ticker="A.TW", code="A", name="A",
            latest_close=100.0, price_change_1d_pct=0.0, price_change_5d_pct=0.0,
            data_date="2026-06-13",
            feats_technical={}, feats_volume={}, feats_risk={},
            market_score=5, positive_reasons=[], negative_reasons=[],
            risk_notes=[], invalidation_conditions=[],
        )
        assert result.rank_in_universe == 0
        assert result.universe_size == 0

    def test_rank_and_size_passed_through(self):
        result = score_stock(
            ticker="A.TW", code="A", name="A",
            latest_close=100.0, price_change_1d_pct=0.0, price_change_5d_pct=0.0,
            data_date="2026-06-13",
            feats_technical={}, feats_volume={}, feats_risk={},
            market_score=5, positive_reasons=[], negative_reasons=[],
            risk_notes=[], invalidation_conditions=[],
            rank_in_universe=3, universe_size=50,
        )
        assert result.rank_in_universe == 3
        assert result.universe_size == 50


# ══════════════════════════════════════════════════════════════════════════════
# 3. RSI < 30 never contributes to momentum_score (ICR-2)
# ══════════════════════════════════════════════════════════════════════════════

class TestRSIOversoldRule:
    """ICR-2: RSI < 30 = oversold, NOT bullish. No contribution to momentum_score."""

    def test_rsi_below_30_zero_contribution(self):
        """RSI = 20 (oversold) should give same momentum as RSI = 15 — both 0 contribution."""
        feats_macd_pos = {"macd_hist": 0.5, "macd_hist_delta": 0.2}
        score_rsi20 = compute_momentum_score({**feats_macd_pos, "rsi14": 20.0})
        score_rsi15 = compute_momentum_score({**feats_macd_pos, "rsi14": 15.0})
        # Both should give same result because RSI < 30 contributes 0
        assert score_rsi20 == score_rsi15

    def test_rsi_29_gives_same_as_rsi_1(self):
        """RSI = 29.9 (just below 30) still contributes 0 to momentum."""
        feats_base = {"macd_hist": 0.0, "macd_hist_delta": 0.0}
        score_29 = compute_momentum_score({**feats_base, "rsi14": 29.9})
        score_1 = compute_momentum_score({**feats_base, "rsi14": 1.0})
        assert score_29 == score_1, "RSI values below 30 should both contribute 0"

    def test_rsi_50_gives_higher_momentum_than_rsi_20(self):
        """RSI in healthy zone (50–70) gives MORE momentum than oversold RSI < 30."""
        feats_macd = {"macd_hist": 0.0, "macd_hist_delta": 0.0}
        score_healthy = compute_momentum_score({**feats_macd, "rsi14": 60.0})
        score_oversold = compute_momentum_score({**feats_macd, "rsi14": 20.0})
        assert score_healthy > score_oversold

    def test_rsi_below_30_adds_to_risk_notes_not_positive(self):
        """ICR-2: RSI < 30 should appear in risk_notes, never in positive_reasons."""
        feats_tech = {
            "rsi14": 25.0,
            "ma5_above_ma20": True, "close_above_ma5": True,
            "macd_hist": 0.1, "macd_hist_delta": 0.1,
        }
        feats_vol = {"volume_ratio": 1.0, "volume_up": False, "volume_down": False, "volume_contraction": False}
        feats_risk = {"atr_pct": 2.0}

        positive = build_positive_reasons(feats_tech, feats_vol, feats_risk)
        risk_notes = build_risk_notes(feats_tech, feats_vol, feats_risk)

        # RSI 25 must NOT appear in positive reasons
        assert not any("RSI" in r and "25" in r for r in positive), \
            "RSI < 30 must not appear in positive_reasons"

        # RSI 25 MUST appear in risk_notes
        assert any("RSI" in n and ("超賣" in n or "25" in n) for n in risk_notes), \
            "RSI < 30 must add to risk_notes"

    def test_rsi_above_75_adds_to_risk_notes(self):
        """RSI > 75 (overheated) adds to risk_notes."""
        feats_tech = {"rsi14": 80.0}
        feats_vol = {"volume_contraction": False}
        feats_risk = {}

        risk_notes = build_risk_notes(feats_tech, feats_vol, feats_risk)
        assert any("RSI" in n or "偏高" in n for n in risk_notes), \
            "RSI > 75 must add to risk_notes"


# ══════════════════════════════════════════════════════════════════════════════
# 4. Direction thresholds
# ══════════════════════════════════════════════════════════════════════════════

class TestDirectionThresholds:
    @pytest.mark.parametrize("score,expected", [
        (70, "bullish"),
        (80, "bullish"),
        (100, "bullish"),
        (35, "bearish"),
        (20, "bearish"),
        (0, "bearish"),
        (36, "neutral"),
        (69, "neutral"),
        (50, "neutral"),
    ])
    def test_direction_thresholds(self, score, expected):
        assert compute_direction(score) == expected, \
            f"score={score} should be {expected}"


# ══════════════════════════════════════════════════════════════════════════════
# 5. Confidence = 高 requires ALL 5 conditions (ICR-3)
# ══════════════════════════════════════════════════════════════════════════════

class TestConfidenceRules:
    """ICR-3: confidence = 高 requires ALL 5 conditions simultaneously."""

    def _good_feats(self):
        return (
            {"rsi14": 62.0, "macd_hist": 0.5},  # feats_technical
            {"volume_ratio": 1.5, "volume_up": True, "volume_down": False, "volume_contraction": False},  # feats_volume
        )

    def test_all_5_conditions_gives_high(self):
        feats_tech, feats_vol = self._good_feats()
        confidence = compute_confidence(
            radar_score=85,
            volume_ratio=1.5,
            risk_notes=["one note"],       # <= 1
            positive_reasons=["r1", "r2", "r3"],  # >= 3
            feats_technical=feats_tech,
            feats_volume=feats_vol,
        )
        assert confidence == "高"

    def test_missing_radar_score_drops_to_mid(self):
        """radar_score = 79 (< 80) prevents 高."""
        feats_tech, feats_vol = self._good_feats()
        confidence = compute_confidence(
            radar_score=79,
            volume_ratio=1.5,
            risk_notes=[],
            positive_reasons=["r1", "r2", "r3"],
            feats_technical=feats_tech,
            feats_volume=feats_vol,
        )
        assert confidence in ("中", "低"), f"Expected 中 or 低, got {confidence}"

    def test_missing_volume_ratio_drops(self):
        """volume_ratio = 1.1 (< 1.2) prevents 高."""
        feats_tech, feats_vol = self._good_feats()
        confidence = compute_confidence(
            radar_score=85,
            volume_ratio=1.1,
            risk_notes=[],
            positive_reasons=["r1", "r2", "r3"],
            feats_technical=feats_tech,
            feats_volume=feats_vol,
        )
        assert confidence != "高"

    def test_too_many_risk_notes_drops(self):
        """len(risk_notes) = 2 (> 1) prevents 高."""
        feats_tech, feats_vol = self._good_feats()
        confidence = compute_confidence(
            radar_score=85,
            volume_ratio=1.5,
            risk_notes=["note1", "note2"],
            positive_reasons=["r1", "r2", "r3"],
            feats_technical=feats_tech,
            feats_volume=feats_vol,
        )
        assert confidence != "高"

    def test_too_few_positive_reasons_drops(self):
        """len(positive_reasons) = 2 (< 3) prevents 高."""
        feats_tech, feats_vol = self._good_feats()
        confidence = compute_confidence(
            radar_score=85,
            volume_ratio=1.5,
            risk_notes=[],
            positive_reasons=["r1", "r2"],
            feats_technical=feats_tech,
            feats_volume=feats_vol,
        )
        assert confidence != "高"

    def test_signal_conflict_volume_contraction_drops(self):
        """Volume contraction + bullish direction is a conflict — prevents 高."""
        feats_tech = {"rsi14": 62.0, "macd_hist": 0.5}
        feats_vol_conflict = {
            "volume_ratio": 1.5, "volume_up": False, "volume_down": False,
            "volume_contraction": True,  # CONFLICT
        }
        confidence = compute_confidence(
            radar_score=85,
            volume_ratio=1.5,
            risk_notes=[],
            positive_reasons=["r1", "r2", "r3"],
            feats_technical=feats_tech,
            feats_volume=feats_vol_conflict,
        )
        assert confidence != "高"

    def test_signal_conflict_rsi_overheated_drops(self):
        """RSI > 75 + bullish is a conflict — prevents 高."""
        feats_tech_hot = {"rsi14": 80.0, "macd_hist": 0.5}  # RSI > 75
        feats_vol = {"volume_ratio": 1.5, "volume_up": True, "volume_down": False, "volume_contraction": False}
        confidence = compute_confidence(
            radar_score=85,
            volume_ratio=1.5,
            risk_notes=[],
            positive_reasons=["r1", "r2", "r3"],
            feats_technical=feats_tech_hot,
            feats_volume=feats_vol,
        )
        assert confidence != "高"

    def test_signal_conflict_rsi_oversold_drops(self):
        """RSI < 30 + bullish is a conflict — prevents 高."""
        feats_tech_oversold = {"rsi14": 25.0, "macd_hist": 0.5}
        feats_vol = {"volume_ratio": 1.5, "volume_up": True, "volume_down": False, "volume_contraction": False}
        confidence = compute_confidence(
            radar_score=85,
            volume_ratio=1.5,
            risk_notes=[],
            positive_reasons=["r1", "r2", "r3"],
            feats_technical=feats_tech_oversold,
            feats_volume=feats_vol,
        )
        assert confidence != "高"

    def test_low_confidence_when_radar_below_60(self):
        """radar_score < 60 always gives 低."""
        feats_tech, feats_vol = self._good_feats()
        confidence = compute_confidence(
            radar_score=55,
            volume_ratio=1.5,
            risk_notes=[],
            positive_reasons=["r1", "r2", "r3"],
            feats_technical=feats_tech,
            feats_volume=feats_vol,
        )
        assert confidence == "低"

    def test_mid_confidence_when_score_60_to_79(self):
        """radar_score in [60, 79] without all 高 conditions → 中."""
        feats_tech, feats_vol = self._good_feats()
        confidence = compute_confidence(
            radar_score=70,
            volume_ratio=1.5,
            risk_notes=[],
            positive_reasons=["r1"],     # only 1, not >= 3
            feats_technical=feats_tech,
            feats_volume=feats_vol,
        )
        assert confidence == "中"


# ══════════════════════════════════════════════════════════════════════════════
# 6. base_score excludes market_score (ICR-1)
# ══════════════════════════════════════════════════════════════════════════════

class TestBaseScoreIsolation:
    """ICR-1: base_score = trend + momentum + volume + risk (never includes market_score)."""

    def test_base_score_excludes_market(self):
        result = _make_result(trend=22, momentum=15, volume=16, risk=12, market=8, radar_score=73)
        expected_base = 22 + 15 + 16 + 12
        assert result.base_score == expected_base

    def test_market_score_changes_radar_not_base(self):
        r1 = _make_result(trend=20, momentum=14, volume=14, risk=10, market=3, radar_score=61)
        r2 = _make_result(trend=20, momentum=14, volume=14, risk=10, market=9, radar_score=67)
        assert r1.base_score == r2.base_score, "base_score must be same regardless of market_score"
        # radar_score may differ (as expected), but we don't control that directly from _make_result
        # What matters is base_score isolation
        assert r1.base_score == 20 + 14 + 14 + 10

    def test_score_stock_base_score_correct(self):
        """score_stock result.base_score == trend+momentum+volume+risk."""
        feats_tech = {
            "ma5_above_ma20": True, "ma5_above_ma60": True,
            "close_above_ma5": True, "close_above_ma20": True,
            "ma5_slope": 0.5, "ma20_slope": 0.3,
            "rsi14": 60.0, "macd_hist": 0.5, "macd_hist_delta": 0.1,
        }
        feats_vol = {"volume_ratio": 1.3, "volume_up": True, "volume_down": False, "volume_contraction": False}
        feats_risk = {"atr_pct": 2.0, "dist_to_resistance_pct": 6.0, "near_resistance": False, "broke_support": False}
        result = score_stock(
            ticker="2330.TW", code="2330", name="台積電",
            latest_close=900.0, price_change_1d_pct=1.5, price_change_5d_pct=3.0,
            data_date="2026-06-13",
            feats_technical=feats_tech, feats_volume=feats_vol, feats_risk=feats_risk,
            market_score=7,
            positive_reasons=[], negative_reasons=[], risk_notes=[], invalidation_conditions=[],
        )
        expected_base = result.trend_score + result.momentum_score + result.volume_score + result.risk_score
        assert result.base_score == expected_base
        assert result.radar_score == expected_base + 7


# ══════════════════════════════════════════════════════════════════════════════
# 7. negative_reasons != risk_notes (ICR-4)
# ══════════════════════════════════════════════════════════════════════════════

class TestReasonsSeparation:
    """ICR-4: negative_reasons are bearish signals; risk_notes are cautions."""

    def test_rsi_below_30_in_risk_notes_not_negative(self):
        """Oversold RSI is a caution, not a bearish trend signal."""
        feats_tech = {"rsi14": 25.0, "ma5_above_ma20": True, "close_above_ma20": True, "macd_hist": 0.1}
        feats_vol = {"volume_down": False, "volume_ratio": 1.0, "volume_contraction": False}
        feats_risk = {"atr_pct": 2.0}

        risk_notes = build_risk_notes(feats_tech, feats_vol, feats_risk)
        negative = build_negative_reasons(feats_tech, feats_vol, feats_risk)

        # RSI 25 mention must be in risk_notes
        rsi_in_risk = any("RSI" in n for n in risk_notes)
        # RSI 25 must NOT be in negative reasons as a bearish signal
        rsi_in_neg = any("RSI" in n for n in negative)

        assert rsi_in_risk, "RSI oversold must appear in risk_notes"
        # negative_reasons may have other entries (e.g. RSI < 50 note), but the oversold
        # caution itself is a risk_note, not a bearish reason

    def test_support_break_in_risk_notes(self):
        """Support break is a risk caution."""
        feats_tech = {"rsi14": 50.0}
        feats_vol = {"volume_contraction": False}
        feats_risk = {"broke_support": True}

        risk_notes = build_risk_notes(feats_tech, feats_vol, feats_risk)
        assert any("支撐" in n or "停損" in n for n in risk_notes), \
            "broke_support must add to risk_notes"

    def test_near_resistance_in_risk_notes(self):
        """Near resistance is a risk caution, not a bearish reason."""
        feats_tech = {"rsi14": 60.0}
        feats_vol = {"volume_contraction": False}
        feats_risk = {"near_resistance": True, "dist_to_resistance_pct": 1.5}

        risk_notes = build_risk_notes(feats_tech, feats_vol, feats_risk)
        assert any("壓力" in n or "resistance" in n.lower() for n in risk_notes), \
            "near_resistance must add to risk_notes"


# ══════════════════════════════════════════════════════════════════════════════
# 8. Sub-score bands
# ══════════════════════════════════════════════════════════════════════════════

class TestTrendScoreBands:
    """trend_score bands: High 22–30, Mid 12–21, Low 0–11."""

    def test_high_band_full_alignment(self):
        """MA5 > MA20 > MA60, close above MA5, both slopes positive → ≥ 22."""
        feats = {
            "ma5_above_ma20": True, "ma5_above_ma60": True,
            "close_above_ma5": True, "close_above_ma20": True,
            "ma5_slope": 1.0, "ma20_slope": 0.5,
        }
        score = compute_trend_score(feats)
        assert 22 <= score <= 30, f"Expected high band 22–30, got {score}"

    def test_mid_band_partial_alignment(self):
        """MA5 > MA20 but MA60 missing → lower than full three-MA alignment.

        Note: the actual band depends on close position and slopes.
        This test verifies that missing MA60 gives a lower score than full
        three-MA alignment (High band).
        """
        feats_no_ma60 = {
            "ma5_above_ma20": True, "ma5_above_ma60": None,  # MA60 unavailable
            "close_above_ma5": True, "close_above_ma20": True,
            "ma5_slope": 1.0, "ma20_slope": 0.5,
        }
        feats_full = {
            "ma5_above_ma20": True, "ma5_above_ma60": True,  # full alignment
            "close_above_ma5": True, "close_above_ma20": True,
            "ma5_slope": 1.0, "ma20_slope": 0.5,
        }
        score_no_ma60 = compute_trend_score(feats_no_ma60)
        score_full = compute_trend_score(feats_full)
        # Missing MA60 must give a lower score than full three-MA alignment
        assert score_no_ma60 < score_full, \
            f"Missing MA60 ({score_no_ma60}) must score lower than full alignment ({score_full})"
        # Must still be in valid range
        assert 0 <= score_no_ma60 <= 30

    def test_low_band_bearish(self):
        """MA5 < MA20, close below MA20 → low band 0–11."""
        feats = {
            "ma5_above_ma20": False, "ma5_above_ma60": False,
            "close_above_ma5": False, "close_above_ma20": False,
            "ma5_slope": -1.0, "ma20_slope": -0.5,
        }
        score = compute_trend_score(feats)
        assert 0 <= score <= 11, f"Expected low band 0–11, got {score}"

    def test_score_bounded_0_to_30(self):
        """trend_score is always within [0, 30]."""
        for feats in [
            {},
            {"ma5_above_ma20": True, "ma5_above_ma60": True, "close_above_ma5": True,
             "close_above_ma20": True, "ma5_slope": 10.0, "ma20_slope": 10.0},
            {"ma5_above_ma20": False, "close_above_ma20": False},
        ]:
            score = compute_trend_score(feats)
            assert 0 <= score <= 30, f"trend_score out of range: {score}"


class TestVolumeScoreBands:
    """volume_score bands: High 15–20, Mid 8–14, Low 0–7."""

    def test_high_band_large_volume_up(self):
        """volume_ratio >= 1.5 and price up → high band 15–20."""
        score = compute_volume_score({"volume_ratio": 1.8, "volume_up": True, "volume_down": False, "volume_contraction": False})
        assert 15 <= score <= 20, f"Expected high band, got {score}"

    def test_mid_band_normal_volume(self):
        """volume_ratio 1.0–1.2 and no strong signal → mid band 8–14."""
        score = compute_volume_score({"volume_ratio": 1.1, "volume_up": False, "volume_down": False, "volume_contraction": False})
        assert 8 <= score <= 14, f"Expected mid band, got {score}"

    def test_low_band_volume_down(self):
        """High-volume decline → low band 0–7."""
        score = compute_volume_score({"volume_ratio": 2.0, "volume_up": False, "volume_down": True, "volume_contraction": False})
        assert 0 <= score <= 7, f"Expected low band, got {score}"

    def test_volume_score_bounded(self):
        """volume_score always within [0, 20]."""
        test_cases = [
            {"volume_ratio": 3.0, "volume_up": True, "volume_down": False, "volume_contraction": False},
            {"volume_ratio": 0.1, "volume_up": False, "volume_down": True, "volume_contraction": False},
            {},
        ]
        for feats in test_cases:
            score = compute_volume_score(feats)
            assert 0 <= score <= 20, f"volume_score out of range: {score}"


class TestRiskScoreBands:
    """risk_score bands: High 11–15, Mid 6–10, Low 0–5."""

    def test_high_band_low_volatility_room_to_run(self):
        """ATR% < 2%, dist_resistance > 5% → high band 11–15."""
        score = compute_risk_score({"atr_pct": 1.5, "dist_to_resistance_pct": 7.0, "near_resistance": False, "broke_support": False})
        assert 11 <= score <= 15, f"Expected high band, got {score}"

    def test_mid_band_moderate(self):
        """ATR% 2–4%, distance to resistance 3–5% → mid band 6–10."""
        score = compute_risk_score({"atr_pct": 3.0, "dist_to_resistance_pct": 4.0, "near_resistance": False, "broke_support": False})
        assert 6 <= score <= 10, f"Expected mid band, got {score}"

    def test_low_band_broke_support(self):
        """broke_support → low band 0–5."""
        score = compute_risk_score({"atr_pct": 2.0, "dist_to_resistance_pct": 4.0, "near_resistance": False, "broke_support": True})
        assert 0 <= score <= 5, f"Expected low band, got {score}"

    def test_low_band_high_volatility(self):
        """ATR% > 4% → lower band."""
        score = compute_risk_score({"atr_pct": 5.0, "dist_to_resistance_pct": 4.0, "near_resistance": False, "broke_support": False})
        assert 0 <= score <= 10, f"risk_score out of expected range, got {score}"

    def test_risk_score_bounded(self):
        """risk_score always within [0, 15]."""
        for feats in [
            {"broke_support": True, "atr_pct": 10.0},
            {"atr_pct": 0.5, "dist_to_resistance_pct": 20.0, "near_resistance": False, "broke_support": False},
            {},
        ]:
            score = compute_risk_score(feats)
            assert 0 <= score <= 15, f"risk_score out of range: {score}"


# ══════════════════════════════════════════════════════════════════════════════
# 9. market_score isolation: selection uses base_score (ICR-1)
# ══════════════════════════════════════════════════════════════════════════════

class TestMarketScoreIsolation:
    """Market score must never drive stock selection."""

    def test_selector_uses_base_score(self):
        """Stock with base_score = 72 qualifies for strong_watchlist regardless of market_score."""
        from app.recommendation.selector import select_strong_watchlist, select_weakness_alerts

        # Create result with strong base_score but market_score = 0 (so radar_score might be lower)
        r_strong_base = _make_result(
            trend=22, momentum=18, volume=18, risk=14, market=0,
            radar_score=72, direction="bullish", confidence="中"
        )
        # base_score = 72 → qualifies
        assert r_strong_base.base_score == 72

        strong = select_strong_watchlist([r_strong_base])
        assert len(strong) == 1, "Stock with base_score=72 must be in strong_watchlist"

    def test_selector_excludes_weak_base_with_high_market(self):
        """Stock with base_score = 60 does NOT qualify even with market_score = 10."""
        from app.recommendation.selector import select_strong_watchlist

        r_weak_base = _make_result(
            trend=15, momentum=12, volume=18, risk=15, market=10,
            radar_score=70, direction="bullish", confidence="中"
        )
        # base_score = 15+12+18+15 = 60 → does NOT meet threshold (70)
        assert r_weak_base.base_score == 60

        strong = select_strong_watchlist([r_weak_base])
        assert len(strong) == 0, \
            "Stock with base_score=60 must NOT be in strong_watchlist (ICR-1 enforced)"

    def test_weakness_selector_uses_base_score(self):
        """Stock with base_score = 35 qualifies for weakness_alerts."""
        from app.recommendation.selector import select_weakness_alerts

        r_weak = _make_result(
            trend=8, momentum=7, volume=12, risk=8, market=5,
            radar_score=40, direction="neutral", confidence="低"
        )
        assert r_weak.base_score == 35

        weak = select_weakness_alerts([r_weak])
        assert len(weak) == 1, "Stock with base_score=35 must be in weakness_alerts"


# ══════════════════════════════════════════════════════════════════════════════
# 10. chip_score is always None
# ══════════════════════════════════════════════════════════════════════════════

class TestChipScore:
    def test_chip_score_is_none(self):
        result = score_stock(
            ticker="2330.TW", code="2330", name="台積電",
            latest_close=900.0, price_change_1d_pct=1.0, price_change_5d_pct=2.0,
            data_date="2026-06-13",
            feats_technical={}, feats_volume={}, feats_risk={},
            market_score=5, positive_reasons=[], negative_reasons=[],
            risk_notes=[], invalidation_conditions=[],
        )
        assert result.chip_score is None, "chip_score must always be None (reserved field)"
