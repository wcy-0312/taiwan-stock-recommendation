# Scoring Specification — 台股技術雷達 V2

**Version:** 2.0  
**Date:** 2026-06-13  
**Status:** Authoritative

---

## Overview

The radar scoring system produces a composite score (0–100) for each stock in the tw0050 universe. The score is composed of five sub-scores:

| Sub-score | Max | Description |
|-----------|-----|-------------|
| trend_score | 30 | Moving average alignment, price position relative to MAs |
| momentum_score | 20 | MACD histogram, RSI |
| volume_score | 20 | Volume ratio, buy/sell volume patterns |
| risk_score | 15 | Volatility (ATR), distance to resistance/support |
| market_score | 10 | Universe-level market environment (context only) |
| **radar_score** | **100** | Sum of all five, clamped to [0, 100] |

---

## Critical Rules (Information Continuity Requirements)

| ID | Rule | Enforcement |
|----|------|-------------|
| ICR-1 | Stock selection uses **base_score** (trend+momentum+volume+risk), **NOT radar_score** | `selector.py` uses `result.base_score`, never `result.radar_score` |
| ICR-2 | RSI < 30 = **oversold, NOT bullish**. Adds to `risk_notes` only, never to `momentum_score` | `radar.py::compute_momentum_score` — RSI < 30 contribution is 0 |
| ICR-3 | confidence = 高 requires **ALL 5 conditions simultaneously** | `radar.py::compute_confidence` — all five checks are AND conditions |
| ICR-4 | `negative_reasons` ≠ `risk_notes`: negatives are bearish signals; risk_notes are cautions even for bullish stocks | `reasons.py` — separate functions for each |

---

## Sub-score Bands

### trend_score (0–30)

Measures the alignment of moving averages and price position.

| Band | Score Range | Conditions |
|------|-------------|------------|
| High | 22–30 | MA5 > MA20 > MA60, close > MA5, MA5 slope > 0, MA20 slope > 0 |
| Mid  | 12–21 | MA5 > MA20 but MA60 missing or not fully aligned, OR close near MA5 |
| Low  | 0–11  | MA5 < MA20, OR close < MA20 |

**Scoring breakdown:**
- Base (MA5 > MA20): +14
- MA60 aligned (MA5 > MA60): +5
- Close above MA5: +4
- Close above MA20 (but not MA5): +2
- MA5 slope > 0: +3
- MA20 slope > 0: +2
- MA5 < MA20, close above MA20: 8
- MA5 < MA20, close below MA20: 2

---

### momentum_score (0–20)

Measures short-term price momentum using MACD histogram and RSI.

| Band | Score Range | Conditions |
|------|-------------|------------|
| High | 15–20 | MACD hist > 0 and expanding (delta > 0), RSI 50–70 |
| Mid  | 8–14  | MACD hist > 0 but flat, OR RSI 70–75 (slightly hot) |
| Low  | 0–7   | MACD hist < 0, OR RSI < 50 |

**RSI Rules (ICR-2 Strict Compliance):**

| RSI Range | Interpretation | Action |
|-----------|----------------|--------|
| 50–70 | Healthy bull zone | +8 to momentum_score |
| 70–75 | Slightly hot, still valid | +4 to momentum_score |
| > 75 | Overheated | 0 to momentum_score + add to `risk_notes` |
| 45–50 | Borderline neutral | +1 to momentum_score |
| 30–45 | Neutral-weak | 0 to momentum_score |
| < 30 | **Oversold** | **0 to momentum_score** + **add to `risk_notes`** — NOT bullish |

**MACD breakdown:**
- Positive histogram: +8
- Expanding positive histogram (delta > 0): additional +4
- Negative histogram: +0

---

### volume_score (0–20)

Measures volume quality relative to price direction.

| Band | Score Range | Conditions |
|------|-------------|------------|
| High | 15–20 | volume_ratio ≥ 1.5 and price up (volume_up = True) |
| Mid  | 8–14  | volume_ratio 1.0–1.5, normal activity |
| Low  | 0–7   | volume_ratio < 0.8 (volume contraction), OR high-volume decline |

**Scoring breakdown:**
- volume_down (high-volume decline): 2
- volume_contraction (ratio < 0.8): 5
- volume_up with ratio ≥ 2.0: 19
- volume_up with ratio ≥ 1.5: 16
- volume_up with ratio < 1.5: 14
- Normal, ratio ≥ 1.2: 13
- Normal, ratio ≥ 1.0: 10
- Normal, ratio ≥ 0.8: 8
- Normal, ratio < 0.8: 5

---

### risk_score (0–15)

Measures trade risk based on volatility and price position relative to support/resistance.

| Band | Score Range | Conditions |
|------|-------------|------------|
| High | 11–15 | ATR% < 2%, distance to resistance > 5%, above support |
| Mid  | 6–10  | ATR% 2–4%, distance to resistance 3–5% |
| Low  | 0–5   | ATR% > 4%, near resistance (< 3% away), OR broke support |

**Scoring breakdown:**
- broke_support: immediately returns 2
- ATR% < 2%: base score 12
- ATR% 2–3%: base score 10
- ATR% 3–4%: base score 7
- ATR% ≥ 4%: base score 4
- near_resistance (< ~3% away): -3
- dist_resistance > 5%: +2
- dist_resistance > 3%: +1

---

### market_score (0–10)

Universe-level market context score. Computed from the distribution of base_scores across all stocks.

**Critical isolation rule (ICR-1):**
> market_score is added to radar_score for display only. It is **never** used for stock selection. The selection gate uses `base_score = trend + momentum + volume + risk`.
>
> If `base_score ≤ 65`, market_score CANNOT push radar_score ≥ 70 in a way that qualifies a stock for `strong_watchlist`. The `selector.py` enforces this by filtering on `base_score >= 70` directly.

| market_score | Condition |
|--------------|-----------|
| 9 | ≥ 60% stocks bullish AND avg_base_score ≥ 65 |
| 8 | ≥ 50% stocks bullish AND avg_base_score ≥ 60 |
| 7 | ≥ 40% stocks bullish AND avg_base_score ≥ 55 |
| 6 | ≥ 30% stocks bullish AND avg_base_score ≥ 50 |
| 5 | ≥ 20% stocks bullish (default neutral) |
| 4 | ≥ 15% bullish AND avg ≥ 45 |
| 3 | ≥ 10% bullish |
| 2 | avg ≥ 40 |
| 1 | otherwise |

---

## Direction Thresholds

| Direction | radar_score Range | Chinese Label |
|-----------|-------------------|---------------|
| `bullish` | ≥ 70 | 多頭 |
| `neutral` | 36–69 | 中性 |
| `bearish` | ≤ 35 | 空頭 |

---

## Confidence Levels

### 高 — Requires ALL 5 Conditions Simultaneously (ICR-3)

1. `radar_score >= 80`
2. `volume_ratio >= 1.2`
3. `len(risk_notes) <= 1`
4. `len(positive_reasons) >= 3`
5. **No signal conflict** (all of the following must be absent):
   - volume contraction + bullish direction
   - RSI > 75 + bullish direction (overheated)
   - RSI < 30 + bullish direction (oversold ≠ bullish)

### 中 — Moderate Confidence

Conditions: Does **not** meet all 高 conditions AND `radar_score >= 60` AND no signal conflict.

### 低 — Low Confidence

Any of:
- `radar_score < 60`
- Any signal conflict exists (even with high radar_score)

---

## Reasons and Risk Notes

### positive_reasons

Bullish signal descriptions generated by `reasons.py::build_positive_reasons()`.

Examples:
- 多頭排列：MA5 > MA20 > MA60，股價站上均線
- MACD 柱狀體持續擴大，上漲動能增強
- RSI 62.0 處於健康多頭區間（50–70）
- 放量上漲（量比 1.8x），為強勢買盤訊號

### negative_reasons

Bearish signal descriptions generated by `reasons.py::build_negative_reasons()`.

ICR-4: These indicate actual bearish trend, not just cautions.

Examples:
- 空頭排列：MA5 < MA20，短線動能偏弱
- MACD 柱狀體持續縮大（負值擴大），下跌動能增強
- RSI 42.0 跌破 50 中線，動能偏弱

### risk_notes

Caution descriptions generated by `reasons.py::build_risk_notes()`.

ICR-4: These can appear even for bullish stocks.

Examples (with ICR-2 noted):
- **RSI 25.0 進入超賣區（< 30）：市場高波動，非進場訊號** ← ICR-2: oversold ≠ bullish
- RSI 80.0 偏高（> 75）：市場情緒偏熱，留意獲利了結風險
- ATR% 4.5% 較高，波動風險偏大，建議控制部位大小
- 接近 20 日壓力位（距壓力 1.8%），注意短線壓力
- 股價跌破 20 日支撐，建議設好停損
- 量能萎縮（量比 0.6x），上漲持續性存疑

### invalidation_conditions

Signal invalidation triggers generated by `reasons.py::build_invalidation_conditions()`.

Examples:
- 收盤跌破 20 日均線（880.00）則訊號失效
- 跌破 20 日支撐（870.00）則停損
- 若突破 20 日壓力（920.00）則可加碼追蹤

---

## Stock Selection Logic

### strong_watchlist

```
base_score >= 70   (NOT radar_score — ICR-1)
sorted: descending by radar_score
max 5 stocks stored, top 3 broadcast
```

### weakness_alerts

```
base_score <= 35   (NOT radar_score — ICR-1)
sorted: ascending by radar_score (weakest first)
max 5 stocks stored, top 2 broadcast
```

### turning_points

Stocks with any of:
- MACD histogram flipped positive (positive_reasons contains "翻正" or "轉折向上")
- MACD histogram flipped negative (negative_reasons contains "翻負" or "轉折向下")

Sorted by `abs(radar_score - 50)` descending (most decisive first).

---

## base_score Property

```python
@property
def base_score(self) -> int:
    return self.trend_score + self.momentum_score + self.volume_score + self.risk_score
```

Maximum possible base_score: 30 + 20 + 20 + 15 = **85**

---

## chip_score

`chip_score` is always `None`. The field is reserved for future chip data (法人籌碼) when a free data source becomes available. It is never included in base_score or radar_score calculation.

---

## Data Quality

- All `Optional[float]` fields default to `None`, never `NaN`
- Formatter uses `_safe_float()` guards — `nan` and `inf` are replaced with fallback values before display
- yfinance `.TW` suffix is mandatory for all tickers
- `2888.TW` (delisted) is skipped gracefully in data fetching
