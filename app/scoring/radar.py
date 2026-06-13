"""
app/scoring/radar.py — 5-sub-score radar scoring engine.

Scoring rules per docs/superpowers/specs/2026-06-13-taiwan-stock-radar-v2-design.md

Sub-score allocations:
    trend_score    : 0–30
    momentum_score : 0–20
    volume_score   : 0–20
    risk_score     : 0–15
    market_score   : 0–10 (added AFTER base_score, not used for selection)
    radar_score    : 0–100 (clamped)

CRITICAL ICR rules enforced here:
    ICR-1: Selection uses base_score, NOT radar_score
    ICR-2: RSI < 30 → risk_notes only, NEVER to momentum_score
    ICR-3: confidence = 高 requires ALL 5 conditions simultaneously
"""

from __future__ import annotations

from typing import Optional


# ─── Sub-score computation ────────────────────────────────────────────────────

def compute_trend_score(feats_technical: dict) -> int:
    """
    Compute trend_score (0–30).

    Band definitions:
        High (22–30): MA5 > MA20 > MA60, close > MA5, MA5 slope > 0, MA20 slope > 0
        Mid  (12–21): MA5 > MA20 but MA60 missing or not aligned, OR close near MA5
        Low  (0–11) : MA5 < MA20, OR close < MA20
    """
    ma5_above_ma20: bool = feats_technical.get("ma5_above_ma20", False)
    ma5_above_ma60: Optional[bool] = feats_technical.get("ma5_above_ma60")
    close_above_ma5: bool = feats_technical.get("close_above_ma5", False)
    close_above_ma20: bool = feats_technical.get("close_above_ma20", False)
    ma5_slope: Optional[float] = feats_technical.get("ma5_slope")
    ma20_slope: Optional[float] = feats_technical.get("ma20_slope")

    score = 0

    if not ma5_above_ma20:
        # Bearish alignment: MA5 < MA20
        if close_above_ma20:
            score = 8   # at least above MA20
        else:
            score = 2   # both below
    else:
        # MA5 > MA20 — at least mid-trend
        base = 14

        # MA60 alignment
        if ma5_above_ma60 is True:
            base += 5   # full three-MA alignment

        # Close position
        if close_above_ma5:
            base += 4
        elif close_above_ma20:
            base += 2

        # Slope bonus
        if ma5_slope is not None and ma5_slope > 0:
            base += 3
        if ma20_slope is not None and ma20_slope > 0:
            base += 2

        score = base

    return max(0, min(30, score))


def compute_momentum_score(feats_technical: dict) -> int:
    """
    Compute momentum_score (0–20).

    RSI rules (ICR-2 compliance):
        RSI 50–70 : healthy bull → add to score
        RSI 70–75 : slightly hot → small add or neutral
        RSI > 75  : overheated → NO add (goes to risk_notes)
        RSI 30–50 : neutral-weak → no score
        RSI < 30  : oversold → NOT a bullish signal, NO add (goes to risk_notes)

    Band definitions:
        High (15–20): MACD hist > 0 and expanding, RSI 50–70
        Mid  (8–14) : MACD hist > 0 but flat, OR RSI 70–75
        Low  (0–7)  : MACD hist < 0, OR RSI < 50
    """
    rsi14: Optional[float] = feats_technical.get("rsi14")
    macd_hist: Optional[float] = feats_technical.get("macd_hist")
    macd_hist_delta: Optional[float] = feats_technical.get("macd_hist_delta")

    score = 0

    # MACD contribution (0–12)
    if macd_hist is not None:
        if macd_hist > 0:
            score += 8  # positive histogram base
            if macd_hist_delta is not None and macd_hist_delta > 0:
                score += 4  # expanding positive histogram
        elif macd_hist < 0:
            score += 0  # bearish
        # else hist == 0: neutral, 0 contribution

    # RSI contribution (0–8)
    # CRITICAL ICR-2: RSI < 30 NEVER contributes to momentum_score
    if rsi14 is not None:
        if 50 <= rsi14 <= 70:
            score += 8   # healthy bull zone
        elif 70 < rsi14 <= 75:
            score += 4   # slightly hot but still valid
        elif 45 <= rsi14 < 50:
            score += 1   # borderline neutral
        # RSI < 30 (oversold): 0 contribution — NOT bullish (ICR-2)
        # RSI > 75 (overheated): 0 contribution — caution only
        # RSI 30–45: 0 contribution

    return max(0, min(20, score))


def compute_volume_score(feats_volume: dict) -> int:
    """
    Compute volume_score (0–20).

    Band definitions:
        High (15–20): volume_ratio >= 1.5 and price up
        Mid  (8–14) : volume_ratio 1.0–1.5, or normal
        Low  (0–7)  : volume_ratio < 0.8 (contraction), OR high-volume decline
    """
    volume_ratio: Optional[float] = feats_volume.get("volume_ratio")
    volume_up: bool = feats_volume.get("volume_up", False)
    volume_down: bool = feats_volume.get("volume_down", False)
    volume_contraction: bool = feats_volume.get("volume_contraction", False)

    if volume_ratio is None:
        return 10  # neutral default when no volume data

    score = 0

    if volume_down:
        # High-volume decline — very bearish
        score = 2
    elif volume_contraction:
        # Volume drying up — cautious
        score = 5
    elif volume_up:
        # High-volume advance — strong bullish signal
        if volume_ratio >= 2.0:
            score = 19
        elif volume_ratio >= 1.5:
            score = 16
        else:
            score = 14
    else:
        # Normal volume
        if volume_ratio >= 1.2:
            score = 13
        elif volume_ratio >= 1.0:
            score = 10
        elif volume_ratio >= 0.8:
            score = 8
        else:
            score = 5

    return max(0, min(20, score))


def compute_risk_score(feats_risk: dict) -> int:
    """
    Compute risk_score (0–15).

    Band definitions:
        High (11–15): ATR% < 2%, distance to resistance > 5%, above support
        Mid  (6–10) : ATR% 2–4%, distance to resistance 3–5%
        Low  (0–5)  : ATR% > 4%, near resistance (< 3%), OR broke support
    """
    atr_pct: Optional[float] = feats_risk.get("atr_pct")
    dist_resistance: Optional[float] = feats_risk.get("dist_to_resistance_pct")
    near_resistance: bool = feats_risk.get("near_resistance", False)
    broke_support: bool = feats_risk.get("broke_support", False)

    score = 8  # default neutral

    if broke_support:
        return max(0, min(15, 2))

    # ATR% component (0–8)
    if atr_pct is not None:
        if atr_pct < 2.0:
            score = 12
        elif atr_pct < 3.0:
            score = 10
        elif atr_pct < 4.0:
            score = 7
        else:
            score = 4   # high volatility, riskier

    # Resistance distance adjustment (-3 to +3)
    if near_resistance:
        score -= 3
    elif dist_resistance is not None:
        if dist_resistance > 5.0:
            score += 2
        elif dist_resistance > 3.0:
            score += 1

    return max(0, min(15, score))


# ─── Direction and confidence ──────────────────────────────────────────────────

def compute_direction(radar_score: int) -> str:
    """
    Compute direction from radar_score.

    bullish  : radar_score >= 70
    bearish  : radar_score <= 35
    neutral  : 36–69
    """
    if radar_score >= 70:
        return "bullish"
    elif radar_score <= 35:
        return "bearish"
    else:
        return "neutral"


def compute_confidence(
    radar_score: int,
    volume_ratio: Optional[float],
    risk_notes: list[str],
    positive_reasons: list[str],
    feats_technical: dict,
    feats_volume: dict,
) -> str:
    """
    Compute confidence level.

    ICR-3: confidence = 高 requires ALL 5 conditions simultaneously:
        1. radar_score >= 80
        2. volume_ratio >= 1.2
        3. len(risk_notes) <= 1
        4. len(positive_reasons) >= 3
        5. No signal conflict

    Signal conflicts:
        - volume contraction + bullish direction
        - RSI > 75 + bullish direction (overheated)
        - RSI < 30 + bullish direction (oversold ≠ bullish)

    中信心: Does not meet all 高 conditions AND radar_score >= 60
    低信心: radar_score < 60, OR ATR% > 4%, OR obvious signal conflict
    """
    rsi14: Optional[float] = feats_technical.get("rsi14")
    volume_contraction: bool = feats_volume.get("volume_contraction", False)
    atr_pct = None
    # atr_pct is not in feats_technical; pass it if needed — check risk_notes for hint

    # Check for signal conflicts
    direction = compute_direction(radar_score)
    has_conflict = False

    if direction == "bullish":
        if volume_contraction:
            has_conflict = True
        if rsi14 is not None and rsi14 > 75:
            has_conflict = True
        if rsi14 is not None and rsi14 < 30:
            has_conflict = True

    # 高 requires ALL 5 conditions
    if (
        radar_score >= 80
        and volume_ratio is not None and volume_ratio >= 1.2
        and len(risk_notes) <= 1
        and len(positive_reasons) >= 3
        and not has_conflict
    ):
        return "高"

    # 低 conditions
    if radar_score < 60 or has_conflict:
        return "低"

    # 中: radar_score 60–79 without all 高 conditions
    return "中"


# ─── Main scoring entry point ──────────────────────────────────────────────────

def score_stock(
    ticker: str,
    code: str,
    name: str,
    latest_close: float,
    price_change_1d_pct: float,
    price_change_5d_pct: float,
    data_date: str,
    feats_technical: dict,
    feats_volume: dict,
    feats_risk: dict,
    market_score: int,
    positive_reasons: list[str],
    negative_reasons: list[str],
    risk_notes: list[str],
    invalidation_conditions: list[str],
    rank_in_universe: int = 0,
    universe_size: int = 0,
) -> "StockRadarResult":
    """
    Compute all sub-scores and assemble a StockRadarResult.

    Parameters
    ----------
    ticker, code, name, latest_close, price_change_1d_pct, price_change_5d_pct : stock identity/price
    data_date        : YYYY-MM-DD string from yfinance_provider
    feats_technical  : dict from compute_technical_features()
    feats_volume     : dict from compute_volume_features()
    feats_risk       : dict from compute_risk_features()
    market_score     : int 0–10 (computed separately from universe context)
    positive_reasons, negative_reasons, risk_notes, invalidation_conditions : lists of str
    rank_in_universe : 1-based rank (filled in by pipeline after all stocks scored)
    universe_size    : total stocks in universe

    Returns
    -------
    StockRadarResult
    """
    from app.scoring.models import StockRadarResult

    trend_score = compute_trend_score(feats_technical)
    momentum_score = compute_momentum_score(feats_technical)
    volume_score = compute_volume_score(feats_volume)
    risk_score = compute_risk_score(feats_risk)

    # radar_score = base_score + market_score, clamped to [0, 100]
    base_score = trend_score + momentum_score + volume_score + risk_score
    radar_score = max(0, min(100, base_score + market_score))

    direction = compute_direction(radar_score)
    volume_ratio: Optional[float] = feats_volume.get("volume_ratio")
    confidence = compute_confidence(
        radar_score=radar_score,
        volume_ratio=volume_ratio,
        risk_notes=risk_notes,
        positive_reasons=positive_reasons,
        feats_technical=feats_technical,
        feats_volume=feats_volume,
    )

    return StockRadarResult(
        ticker=ticker,
        code=code,
        name=name,
        data_date=data_date,
        latest_close=latest_close,
        price_change_1d_pct=price_change_1d_pct,
        price_change_5d_pct=price_change_5d_pct,
        radar_score=radar_score,
        rank_in_universe=rank_in_universe,
        universe_size=universe_size,
        direction=direction,
        confidence=confidence,
        trend_score=trend_score,
        momentum_score=momentum_score,
        volume_score=volume_score,
        risk_score=risk_score,
        market_score=market_score,
        chip_score=None,
        ma5=feats_technical.get("ma5") or 0.0,
        ma20=feats_technical.get("ma20") or 0.0,
        ma60=feats_technical.get("ma60"),
        rsi14=feats_technical.get("rsi14") or 0.0,
        macd_hist=feats_technical.get("macd_hist") or 0.0,
        macd_hist_delta=feats_technical.get("macd_hist_delta") or 0.0,
        volume_ratio=volume_ratio or 1.0,
        atr14=feats_risk.get("atr14") or 0.0,
        atr_pct=feats_risk.get("atr_pct") or 0.0,
        support_20d=feats_risk.get("support_20d") or 0.0,
        resistance_20d=feats_risk.get("resistance_20d") or 0.0,
        positive_reasons=positive_reasons,
        negative_reasons=negative_reasons,
        risk_notes=risk_notes,
        invalidation_conditions=invalidation_conditions,
    )
