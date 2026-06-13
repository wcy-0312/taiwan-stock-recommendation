"""
app/recommendation/formatter.py — LINE message formatter for V2 radar system.

Formatting rules (from design spec):
    - All fields: use `or` fallback, NEVER output None or nan
    - Numeric: prices to 2 decimal places, percentages to 1 decimal place
    - Sub-score display: 趨勢28｜動能18｜量能17｜風險12｜市場9
    - Disclaimer: 以上僅為量化技術觀察，不構成投資建議。
    - Split into up to 3 messages, each <= 5000 chars

Message structure:
    Message 1: Market context + 強勢觀察 Top 3
    Message 2: 轉弱警示 Top 2 (only if weakness stocks exist)
    Message 3: Summary + disclaimer
"""

from __future__ import annotations

import math
from typing import Optional

from app.scoring.models import StockRadarResult
from app.config import LINE_MESSAGE_MAX_CHARS, LINE_MESSAGE_MAX_PARTS


# ─── Safe value formatting ──────────────────────────────────────────────────

def _safe_float(value, fallback: float = 0.0) -> float:
    """Return float, replacing None/NaN/Inf with fallback."""
    if value is None:
        return fallback
    try:
        v = float(value)
        if math.isnan(v) or math.isinf(v):
            return fallback
        return v
    except (TypeError, ValueError):
        return fallback


def _fmt_price(value, fallback: float = 0.0) -> str:
    """Format a price to 2 decimal places; never None/nan."""
    return f"{_safe_float(value, fallback):.2f}"


def _fmt_pct(value, fallback: float = 0.0) -> str:
    """Format a percentage to 1 decimal place with % suffix; never None/nan."""
    return f"{_safe_float(value, fallback):.1f}%"


def _fmt_score(value, fallback: int = 0) -> str:
    """Format a score as int string; never None/nan."""
    if value is None:
        return str(fallback)
    try:
        v = int(float(value))
        return str(v)
    except (TypeError, ValueError):
        return str(fallback)


def _safe_str(value, fallback: str = "—") -> str:
    """Return str, replacing None/empty with fallback."""
    if value is None:
        return fallback
    s = str(value).strip()
    return s if s else fallback


# ─── Direction / confidence display ─────────────────────────────────────────

_DIRECTION_DISPLAY = {
    "bullish": "多頭",
    "neutral": "中性",
    "bearish": "空頭",
}

_CONFIDENCE_EMOJI = {
    "高": "🟢",
    "中": "🟡",
    "低": "🔴",
}


def _direction_zh(direction: str) -> str:
    return _DIRECTION_DISPLAY.get(direction, "中性")


def _confidence_emoji(confidence: str) -> str:
    return _CONFIDENCE_EMOJI.get(confidence, "🟡")


# ─── Single-stock block formatter ───────────────────────────────────────────

def format_stock_block(result: StockRadarResult, rank: int) -> str:
    """
    Format one stock's data into a multi-line text block.

    Parameters
    ----------
    result : StockRadarResult
    rank   : 1-based rank for display

    Returns
    -------
    str — formatted text block (never contains None or nan)
    """
    name = _safe_str(result.name, result.code)
    code = _safe_str(result.code, "????")
    direction = _direction_zh(_safe_str(result.direction, "neutral"))
    confidence = _safe_str(result.confidence, "低")
    conf_emoji = _confidence_emoji(confidence)

    radar = _fmt_score(result.radar_score)
    close = _fmt_price(result.latest_close)
    chg_1d = _fmt_pct(result.price_change_1d_pct)
    chg_5d = _fmt_pct(result.price_change_5d_pct)

    # Sub-scores
    t_score = _fmt_score(result.trend_score)
    m_score = _fmt_score(result.momentum_score)
    v_score = _fmt_score(result.volume_score)
    r_score = _fmt_score(result.risk_score)
    mk_score = _fmt_score(result.market_score)

    # Indicators
    ma5 = _fmt_price(result.ma5)
    ma20 = _fmt_price(result.ma20)
    rsi = f"{_safe_float(result.rsi14):.1f}"
    vol_ratio = f"{_safe_float(result.volume_ratio, 1.0):.1f}x"

    lines = [
        f"#{rank} {code} {name}",
        f"方向：{direction} | 信心：{conf_emoji}{confidence} | 雷達：{radar}/100",
        f"收盤：{close} | 日漲跌：{chg_1d} | 5日漲跌：{chg_5d}",
        f"趨勢{t_score}｜動能{m_score}｜量能{v_score}｜風險{r_score}｜市場{mk_score}",
        f"MA5:{ma5} MA20:{ma20} RSI:{rsi} 量比:{vol_ratio}",
    ]

    # Positive reasons (max 3)
    pos = [r for r in (result.positive_reasons or []) if r][:3]
    if pos:
        lines.append("✅ " + " ／ ".join(pos[:2]))  # compact: max 2 per line

    # Risk notes (max 2)
    risk = [r for r in (result.risk_notes or []) if r][:2]
    if risk:
        lines.append("⚠️ " + " ／ ".join(risk[:1]))

    return "\n".join(lines)


def format_weak_stock_block(result: StockRadarResult, rank: int) -> str:
    """Format a weakness-alert stock block."""
    name = _safe_str(result.name, result.code)
    code = _safe_str(result.code, "????")
    radar = _fmt_score(result.radar_score)
    close = _fmt_price(result.latest_close)
    chg_1d = _fmt_pct(result.price_change_1d_pct)

    t_score = _fmt_score(result.trend_score)
    m_score = _fmt_score(result.momentum_score)
    v_score = _fmt_score(result.volume_score)
    r_score = _fmt_score(result.risk_score)
    mk_score = _fmt_score(result.market_score)

    lines = [
        f"#{rank} {code} {name}",
        f"雷達：{radar}/100 | 收盤：{close} | 日漲跌：{chg_1d}",
        f"趨勢{t_score}｜動能{m_score}｜量能{v_score}｜風險{r_score}｜市場{mk_score}",
    ]

    # Negative reasons (max 2)
    neg = [r for r in (result.negative_reasons or []) if r][:2]
    if neg:
        lines.append("🔻 " + " ／ ".join(neg[:1]))

    return "\n".join(lines)


# ─── Full broadcast message builder ─────────────────────────────────────────

def build_broadcast_messages(
    strong_stocks: list[StockRadarResult],
    weak_stocks: list[StockRadarResult],
    market_stats: Optional[dict],
    data_date: str,
) -> list[str]:
    """
    Build up to 3 LINE messages for the daily broadcast.

    Parameters
    ----------
    strong_stocks : broadcast-eligible strong stocks (top 3)
    weak_stocks   : broadcast-eligible weakness alerts (top 2)
    market_stats  : dict from compute_market_context_stats(), may be None
    data_date     : YYYY-MM-DD string for the message header

    Returns
    -------
    list[str] — 1 to 3 message strings, each <= LINE_MESSAGE_MAX_CHARS characters

    Formatter rules:
        - Never outputs None or nan in any string
        - Prices: 2 decimal places
        - Percentages: 1 decimal place
        - Sub-scores: 趨勢XX｜動能XX｜量能XX｜風險XX｜市場XX
        - Disclaimer: 以上僅為量化技術觀察，不構成投資建議。
    """
    date_display = _safe_str(data_date, "今日")
    messages: list[str] = []

    # ── Message 1: Market context + strong stocks ─────────────────────────────
    parts_1: list[str] = []

    # Header
    parts_1.append(f"📊 台股技術雷達 {date_display}")
    parts_1.append("─" * 28)

    # Market context
    if market_stats:
        bull_count = int(market_stats.get("bullish_count", 0) or 0)
        universe_sz = int(market_stats.get("universe_size", 0) or 0)
        bull_ratio = _safe_float(market_stats.get("bullish_ratio"), 0.0)
        avg_score = _safe_float(market_stats.get("avg_base_score"), 0.0)
        mkt_score = int(market_stats.get("market_score", 5) or 5)

        if universe_sz > 0:
            parts_1.append(
                f"市場環境：{bull_count}/{universe_sz} 股偏多 "
                f"（{bull_ratio*100:.0f}%）｜市場分數：{mkt_score}/10"
            )
            parts_1.append(f"平均基礎分數：{avg_score:.1f}/85")
    else:
        parts_1.append("市場環境：資料不足")

    parts_1.append("─" * 28)

    # Strong stocks
    if strong_stocks:
        parts_1.append("🏆 強勢觀察")
        for i, stock in enumerate(strong_stocks, start=1):
            parts_1.append(format_stock_block(stock, i))
            if i < len(strong_stocks):
                parts_1.append("· · ·")
    else:
        parts_1.append("今日無明確技術面強勢股")

    msg1 = "\n".join(parts_1)
    messages.append(_truncate(msg1, LINE_MESSAGE_MAX_CHARS))

    # ── Message 2: Weakness alerts (only if any) ──────────────────────────────
    if weak_stocks:
        parts_2: list[str] = []
        parts_2.append(f"⚠️ 轉弱警示 {date_display}")
        parts_2.append("─" * 28)
        for i, stock in enumerate(weak_stocks, start=1):
            parts_2.append(format_weak_stock_block(stock, i))
            if i < len(weak_stocks):
                parts_2.append("· · ·")
        msg2 = "\n".join(parts_2)
        messages.append(_truncate(msg2, LINE_MESSAGE_MAX_CHARS))

    # ── Message 3: Summary + disclaimer ──────────────────────────────────────
    strong_count = len(strong_stocks)
    weak_count = len(weak_stocks)

    parts_3: list[str] = [
        f"📋 今日摘要 {date_display}",
        "─" * 28,
        f"強勢股：{strong_count} 支 | 轉弱股：{weak_count} 支",
        "",
        "以上僅為量化技術觀察，不構成投資建議。",
        "投資有風險，請自行評估。",
    ]

    msg3 = "\n".join(parts_3)
    messages.append(_truncate(msg3, LINE_MESSAGE_MAX_CHARS))

    # Ensure we have at most LINE_MESSAGE_MAX_PARTS messages
    return messages[:LINE_MESSAGE_MAX_PARTS]


def format_single_stock_query(result: StockRadarResult) -> str:
    """
    Format a full radar result for a single-stock query command.
    Used for interactive LINE commands like '查 2330'.

    Returns a single message string <= LINE_MESSAGE_MAX_CHARS.
    Never outputs None or nan.
    """
    name = _safe_str(result.name, result.code)
    code = _safe_str(result.code, "????")
    date = _safe_str(result.data_date, "—")
    direction = _direction_zh(_safe_str(result.direction, "neutral"))
    confidence = _safe_str(result.confidence, "低")
    conf_emoji = _confidence_emoji(confidence)

    radar = _fmt_score(result.radar_score)
    close = _fmt_price(result.latest_close)
    chg_1d = _fmt_pct(result.price_change_1d_pct)
    chg_5d = _fmt_pct(result.price_change_5d_pct)

    t_score = _fmt_score(result.trend_score)
    m_score = _fmt_score(result.momentum_score)
    v_score = _fmt_score(result.volume_score)
    r_score = _fmt_score(result.risk_score)
    mk_score = _fmt_score(result.market_score)

    ma5 = _fmt_price(result.ma5)
    ma20 = _fmt_price(result.ma20)
    ma60_str = f"MA60:{_fmt_price(result.ma60)}" if result.ma60 is not None else ""
    rsi = f"{_safe_float(result.rsi14):.1f}"
    macd_h = f"{_safe_float(result.macd_hist):.4f}"
    vol_ratio = f"{_safe_float(result.volume_ratio, 1.0):.1f}x"
    atr_p = _fmt_pct(result.atr_pct)
    support = _fmt_price(result.support_20d)
    resist = _fmt_price(result.resistance_20d)

    lines = [
        f"📈 {code} {name}（{date}）",
        "─" * 24,
        f"方向：{direction} | 信心：{conf_emoji}{confidence}",
        f"雷達分數：{radar}/100",
        f"排名：{result.rank_in_universe}/{result.universe_size}",
        "─" * 24,
        f"收盤：{close}",
        f"日漲跌：{chg_1d} | 5日漲跌：{chg_5d}",
        "─" * 24,
        "【分項分數】",
        f"趨勢{t_score}｜動能{m_score}｜量能{v_score}｜風險{r_score}｜市場{mk_score}",
        "─" * 24,
        "【技術指標】",
        f"MA5:{ma5} MA20:{ma20}" + (f" {ma60_str}" if ma60_str else ""),
        f"RSI:{rsi} | MACD柱:{macd_h} | 量比:{vol_ratio}",
        f"ATR%:{atr_p} | 支撐:{support} | 壓力:{resist}",
    ]

    # Reasons
    pos = [r for r in (result.positive_reasons or []) if r]
    if pos:
        lines.append("─" * 24)
        lines.append("✅ 正面訊號")
        for p in pos[:4]:
            lines.append(f"  • {p}")

    neg = [r for r in (result.negative_reasons or []) if r]
    if neg:
        lines.append("🔻 負面訊號")
        for n in neg[:3]:
            lines.append(f"  • {n}")

    risk = [r for r in (result.risk_notes or []) if r]
    if risk:
        lines.append("⚠️ 風險提示")
        for rn in risk[:3]:
            lines.append(f"  • {rn}")

    inval = [r for r in (result.invalidation_conditions or []) if r]
    if inval:
        lines.append("📌 失效條件")
        for iv in inval[:2]:
            lines.append(f"  • {iv}")

    lines.append("─" * 24)
    lines.append("以上僅為量化技術觀察，不構成投資建議。")

    full = "\n".join(lines)
    return _truncate(full, LINE_MESSAGE_MAX_CHARS)


def _truncate(text: str, max_chars: int) -> str:
    """Truncate a message to max_chars, appending '...' if needed."""
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 3] + "..."
