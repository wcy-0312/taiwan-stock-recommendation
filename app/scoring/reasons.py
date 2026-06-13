"""
app/scoring/reasons.py — Event-based reasons, risk_notes, and invalidation conditions.

Generates human-readable Chinese strings based on computed feature values.
These are then attached to StockRadarResult.

ICR-4: negative_reasons != risk_notes
  - negative_reasons: bearish reasoning (for stocks being sold / in downtrend)
  - risk_notes: cautions even for bullish stocks (e.g. RSI > 75, near resistance)

ICR-2: RSI < 30 = oversold, NOT bullish. Adds to risk_notes only.
"""

from __future__ import annotations

from typing import Optional


def build_positive_reasons(
    feats_technical: dict,
    feats_volume: dict,
    feats_risk: dict,
) -> list[str]:
    """
    Produce positive/bullish signal reasons.

    Parameters
    ----------
    feats_technical : dict from compute_technical_features()
    feats_volume    : dict from compute_volume_features()
    feats_risk      : dict from compute_risk_features()

    Returns
    -------
    list[str] — bullish signal descriptions
    """
    reasons: list[str] = []

    ma5: Optional[float] = feats_technical.get("ma5")
    ma20: Optional[float] = feats_technical.get("ma20")
    ma60: Optional[float] = feats_technical.get("ma60")
    rsi14: Optional[float] = feats_technical.get("rsi14")
    macd_hist: Optional[float] = feats_technical.get("macd_hist")
    macd_hist_delta: Optional[float] = feats_technical.get("macd_hist_delta")
    macd_crossed_up: bool = feats_technical.get("macd_crossed_up", False)
    close_above_ma5: bool = feats_technical.get("close_above_ma5", False)
    close_above_ma20: bool = feats_technical.get("close_above_ma20", False)
    ma5_above_ma20: bool = feats_technical.get("ma5_above_ma20", False)
    ma5_above_ma60: Optional[bool] = feats_technical.get("ma5_above_ma60")
    ma5_slope: Optional[float] = feats_technical.get("ma5_slope")
    ma20_slope: Optional[float] = feats_technical.get("ma20_slope")

    volume_up: bool = feats_volume.get("volume_up", False)
    volume_ratio: Optional[float] = feats_volume.get("volume_ratio")

    dist_resistance: Optional[float] = feats_risk.get("dist_to_resistance_pct")

    # Trend-based reasons
    if ma5_above_ma20 and ma5_above_ma60 and close_above_ma5:
        reasons.append("多頭排列：MA5 > MA20 > MA60，股價站上均線")
    elif ma5_above_ma20 and close_above_ma5:
        reasons.append("短線均線多頭：MA5 > MA20，股價站上短線均線")
    elif close_above_ma20:
        reasons.append("股價站上 20 日均線，中線偏多")

    if ma5_slope is not None and ma5_slope > 0:
        reasons.append("5 日均線向上揚，短線動能增強")

    if ma20_slope is not None and ma20_slope > 0:
        reasons.append("20 日均線向上，中線趨勢轉佳")

    # Momentum reasons
    if macd_crossed_up:
        reasons.append("MACD 柱狀體翻正，動能出現轉折向上訊號")
    elif macd_hist is not None and macd_hist > 0:
        if macd_hist_delta is not None and macd_hist_delta > 0:
            reasons.append("MACD 柱狀體持續擴大，上漲動能增強")
        else:
            reasons.append("MACD 柱狀體為正，短線偏多格局")

    if rsi14 is not None and 50 <= rsi14 <= 70:
        reasons.append(f"RSI {rsi14:.1f} 處於健康多頭區間（50–70）")

    # Volume reasons
    if volume_up:
        reasons.append(
            f"放量上漲（量比 {volume_ratio:.1f}x），為強勢買盤訊號"
            if volume_ratio is not None else "放量上漲，為強勢買盤訊號"
        )

    # Resistance distance
    if dist_resistance is not None and dist_resistance > 5.0:
        reasons.append(f"距離壓力位 {dist_resistance:.1f}%，上漲空間相對充裕")

    return reasons


def build_negative_reasons(
    feats_technical: dict,
    feats_volume: dict,
    feats_risk: dict,
) -> list[str]:
    """
    Produce negative/bearish signal reasons.

    These represent actual bearish signals (for stocks in downtrend or weakening).
    ICR-4: These are NOT risk cautions — those go in risk_notes.

    Returns
    -------
    list[str] — bearish signal descriptions
    """
    reasons: list[str] = []

    ma5: Optional[float] = feats_technical.get("ma5")
    ma20: Optional[float] = feats_technical.get("ma20")
    rsi14: Optional[float] = feats_technical.get("rsi14")
    macd_hist: Optional[float] = feats_technical.get("macd_hist")
    macd_hist_delta: Optional[float] = feats_technical.get("macd_hist_delta")
    macd_crossed_down: bool = feats_technical.get("macd_crossed_down", False)
    close_above_ma20: bool = feats_technical.get("close_above_ma20", False)
    ma5_above_ma20: bool = feats_technical.get("ma5_above_ma20", False)

    volume_down: bool = feats_volume.get("volume_down", False)
    volume_ratio: Optional[float] = feats_volume.get("volume_ratio")

    # Trend breakdown
    if not ma5_above_ma20:
        if ma5 is not None and ma20 is not None:
            reasons.append("空頭排列：MA5 < MA20，短線動能偏弱")

    if not close_above_ma20:
        reasons.append("股價跌破 20 日均線，中線偏弱")

    # Momentum breakdown
    if macd_crossed_down:
        reasons.append("MACD 柱狀體翻負，動能出現轉折向下訊號")
    elif macd_hist is not None and macd_hist < 0:
        if macd_hist_delta is not None and macd_hist_delta < 0:
            reasons.append("MACD 柱狀體持續縮大（負值擴大），下跌動能增強")
        else:
            reasons.append("MACD 柱狀體為負，短線偏空格局")

    if rsi14 is not None and rsi14 < 50:
        reasons.append(f"RSI {rsi14:.1f} 跌破 50 中線，動能偏弱")

    # Volume selling
    if volume_down:
        reasons.append(
            f"放量下跌（量比 {volume_ratio:.1f}x），為弱勢賣盤訊號"
            if volume_ratio is not None else "放量下跌，為弱勢賣盤訊號"
        )

    return reasons


def build_risk_notes(
    feats_technical: dict,
    feats_volume: dict,
    feats_risk: dict,
) -> list[str]:
    """
    Produce risk notes — cautions even for bullish stocks.

    ICR-2: RSI < 30 (oversold) → adds to risk_notes ONLY, never to positive reasons.
    ICR-4: risk_notes are cautions; they do NOT imply bearish direction.

    Returns
    -------
    list[str] — risk caution strings
    """
    notes: list[str] = []

    rsi14: Optional[float] = feats_technical.get("rsi14")
    volume_contraction: bool = feats_volume.get("volume_contraction", False)
    volume_ratio: Optional[float] = feats_volume.get("volume_ratio")
    atr_pct: Optional[float] = feats_risk.get("atr_pct")
    near_resistance: bool = feats_risk.get("near_resistance", False)
    broke_support: bool = feats_risk.get("broke_support", False)
    dist_resistance: Optional[float] = feats_risk.get("dist_to_resistance_pct")

    # RSI cautions — ICR-2 compliance
    if rsi14 is not None:
        if rsi14 < 30:
            # CRITICAL: RSI < 30 = oversold, NOT bullish signal
            notes.append(f"RSI {rsi14:.1f} 進入超賣區（< 30）：市場高波動，非進場訊號")
        elif rsi14 > 75:
            notes.append(f"RSI {rsi14:.1f} 偏高（> 75）：市場情緒偏熱，留意獲利了結風險")

    # Volatility
    if atr_pct is not None and atr_pct > 4.0:
        notes.append(f"ATR% {atr_pct:.1f}% 較高，波動風險偏大，建議控制部位大小")

    # Resistance proximity
    if near_resistance:
        dist_txt = f"（距壓力 {dist_resistance:.1f}%）" if dist_resistance is not None else ""
        notes.append(f"接近 20 日壓力位{dist_txt}，注意短線壓力")

    # Support break
    if broke_support:
        notes.append("股價跌破 20 日支撐，建議設好停損")

    # Volume contraction with uptrend (suspicious breakout)
    if volume_contraction:
        ratio_txt = f"（量比 {volume_ratio:.1f}x）" if volume_ratio is not None else ""
        notes.append(f"量能萎縮{ratio_txt}，上漲持續性存疑")

    return notes


def build_invalidation_conditions(
    feats_technical: dict,
    feats_risk: dict,
) -> list[str]:
    """
    Produce signal invalidation triggers — conditions that would negate the current signal.

    Returns
    -------
    list[str] — invalidation condition descriptions
    """
    conditions: list[str] = []

    ma20: Optional[float] = feats_technical.get("ma20")
    support_20d: Optional[float] = feats_risk.get("support_20d")
    resistance_20d: Optional[float] = feats_risk.get("resistance_20d")

    if ma20 is not None:
        conditions.append(f"收盤跌破 20 日均線（{ma20:.2f}）則訊號失效")

    if support_20d is not None:
        conditions.append(f"跌破 20 日支撐（{support_20d:.2f}）則停損")

    if resistance_20d is not None:
        conditions.append(f"若突破 20 日壓力（{resistance_20d:.2f}）則可加碼追蹤")

    return conditions
