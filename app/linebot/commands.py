"""
app/linebot/commands.py — Parse and dispatch LINE Bot interactive commands.

Supported commands (case-insensitive, leading/trailing whitespace ignored):

    查 <CODE>       — Query latest radar result for a stock code
    今日雷達         — Return today's broadcast summary from cache
    追蹤 <CODE>     — Add a stock to the user's watchlist
    移除 <CODE>     — Remove a stock from the user's watchlist
    我的清單        — List the user's watchlist
    幫助 / help    — Return the help text

Unknown messages return the help text so the bot is never silent.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime
from typing import Optional

from app.linebot.watchlist import add_ticker, remove_ticker, get_watchlist

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Help text
# ---------------------------------------------------------------------------

HELP_TEXT = (
    "【台股技術雷達 指令說明】\n"
    "─────────────────\n"
    "查 <代號>       查詢個股雷達分析\n"
    "                例：查 2330\n"
    "今日雷達         今日播報摘要\n"
    "追蹤 <代號>     加入我的追蹤清單\n"
    "                例：追蹤 2330\n"
    "移除 <代號>     從清單移除\n"
    "                例：移除 2330\n"
    "我的清單         查看追蹤清單\n"
    "幫助 / help     顯示此說明\n"
    "─────────────────\n"
    "以上僅為量化技術觀察，不構成投資建議。"
)

# ---------------------------------------------------------------------------
# Command patterns
# ---------------------------------------------------------------------------

_RE_QUERY = re.compile(r"^查\s+([A-Za-z0-9]+\.?[A-Za-z]*)$", re.UNICODE)
_RE_ADD = re.compile(r"^追蹤\s+([A-Za-z0-9]+\.?[A-Za-z]*)$", re.UNICODE)
_RE_REMOVE = re.compile(r"^移除\s+([A-Za-z0-9]+\.?[A-Za-z]*)$", re.UNICODE)
_RE_WATCHLIST = re.compile(r"^我的清單$", re.UNICODE)
_RE_TODAY_RADAR = re.compile(r"^今日雷達$", re.UNICODE)
_RE_HELP = re.compile(r"^(幫助|help|Help|HELP)$", re.UNICODE)


# ---------------------------------------------------------------------------
# Normalisation helpers
# ---------------------------------------------------------------------------

def _normalise_code(raw: str) -> str:
    """
    Normalise a user-supplied ticker code.

    Accepts:  "2330", "2330.tw", "2330.TW"
    Returns:  "2330.TW"  (always uppercase, always .TW suffix)
    """
    code = raw.strip().upper()
    if not code.endswith(".TW"):
        code = code + ".TW"
    return code


# ---------------------------------------------------------------------------
# Lazy pipeline import
# ---------------------------------------------------------------------------

def _get_cached_radar(ticker: str) -> Optional[object]:
    """
    Try to load the most recent cached analysis result for a ticker.

    Searches data/cache/analysis_<date>.json (most recent first).
    Returns a StockRadarResult-like dict or None if not found.
    """
    try:
        from app.config import CACHE_DIR
        from app.scoring.models import StockRadarResult

        cache_files = sorted(CACHE_DIR.glob("analysis_*.json"), reverse=True)
        for cache_file in cache_files[:3]:  # check last 3 days
            import json
            with cache_file.open(encoding="utf-8") as fh:
                data = json.load(fh)
            for r in data.get("results", []):
                if r.get("ticker", "").upper() == ticker.upper():
                    # Reconstruct as StockRadarResult
                    return StockRadarResult(
                        ticker=r["ticker"],
                        code=r.get("code", ticker.replace(".TW", "")),
                        name=r.get("name", r.get("code", "")),
                        data_date=r.get("data_date", "—"),
                        latest_close=float(r.get("latest_close") or 0),
                        price_change_1d_pct=float(r.get("price_change_1d_pct") or 0),
                        price_change_5d_pct=float(r.get("price_change_5d_pct") or 0),
                        radar_score=int(r.get("radar_score") or 0),
                        rank_in_universe=int(r.get("rank_in_universe") or 0),
                        universe_size=int(r.get("universe_size") or 0),
                        direction=r.get("direction", "neutral"),
                        confidence=r.get("confidence", "低"),
                        trend_score=int(r.get("trend_score") or 0),
                        momentum_score=int(r.get("momentum_score") or 0),
                        volume_score=int(r.get("volume_score") or 0),
                        risk_score=int(r.get("risk_score") or 0),
                        market_score=int(r.get("market_score") or 0),
                        chip_score=r.get("chip_score"),
                        ma5=float(r.get("ma5") or 0),
                        ma20=float(r.get("ma20") or 0),
                        ma60=r.get("ma60"),
                        rsi14=float(r.get("rsi14") or 0),
                        macd_hist=float(r.get("macd_hist") or 0),
                        macd_hist_delta=float(r.get("macd_hist_delta") or 0),
                        volume_ratio=float(r.get("volume_ratio") or 1.0),
                        atr14=float(r.get("atr14") or 0),
                        atr_pct=float(r.get("atr_pct") or 0),
                        support_20d=float(r.get("support_20d") or 0),
                        resistance_20d=float(r.get("resistance_20d") or 0),
                        positive_reasons=r.get("positive_reasons") or [],
                        negative_reasons=r.get("negative_reasons") or [],
                        risk_notes=r.get("risk_notes") or [],
                        invalidation_conditions=r.get("invalidation_conditions") or [],
                        historical_win_rate_5d=r.get("historical_win_rate_5d"),
                        historical_avg_return_5d=r.get("historical_avg_return_5d"),
                        historical_win_rate_10d=r.get("historical_win_rate_10d"),
                        historical_avg_return_10d=r.get("historical_avg_return_10d"),
                    )
    except Exception as exc:
        logger.warning("_get_cached_radar: could not load cache — %s", exc)
    return None


def _get_today_cached_summary() -> Optional[str]:
    """
    Load today's broadcast summary from cache.
    Returns a single string or None.
    """
    try:
        from app.config import CACHE_DIR
        today = datetime.today().strftime("%Y-%m-%d")
        cache_file = CACHE_DIR / f"analysis_{today}.json"
        if not cache_file.exists():
            return None
        import json
        with cache_file.open(encoding="utf-8") as fh:
            data = json.load(fh)
        market_stats = data.get("market_stats", {})
        results_raw = data.get("results", [])

        # Reconstruct SelectionResult-like info from cache for quick summary
        bull_count = int(market_stats.get("bullish_count") or 0)
        universe_size = int(market_stats.get("universe_size") or len(results_raw))
        mkt_score = int(market_stats.get("market_score") or 5)

        strong = [r for r in results_raw if r.get("direction") == "bullish"][:3]
        weak = [r for r in results_raw if r.get("direction") == "bearish"][:2]

        lines = [
            f"📊 台股技術雷達 {today}",
            "─" * 24,
            f"市場環境：{bull_count}/{universe_size} 偏多｜市場分數：{mkt_score}/10",
            "─" * 24,
        ]
        if strong:
            lines.append("🏆 強勢觀察")
            for i, r in enumerate(strong, 1):
                code = r.get("code", "")
                name = r.get("name", code)
                rs = int(r.get("radar_score") or 0)
                direction = r.get("direction", "neutral")
                lines.append(f"  #{i} {code} {name} 雷達:{rs} 方向:{direction}")
        if weak:
            lines.append("⚠️ 轉弱警示")
            for i, r in enumerate(weak, 1):
                code = r.get("code", "")
                name = r.get("name", code)
                rs = int(r.get("radar_score") or 0)
                lines.append(f"  #{i} {code} {name} 雷達:{rs}")
        lines.append("─" * 24)
        lines.append("以上僅為量化技術觀察，不構成投資建議。")
        return "\n".join(lines)
    except Exception as exc:
        logger.warning("_get_today_cached_summary: error — %s", exc)
        return None


# ---------------------------------------------------------------------------
# Command dispatcher
# ---------------------------------------------------------------------------

def dispatch_command(user_id: str, text: str) -> list[str]:
    """
    Parse a LINE message text and return a list of reply strings.

    Parameters
    ----------
    user_id : str — LINE user_id of the sender (for watchlist operations)
    text    : str — raw message text from the LINE webhook event

    Returns
    -------
    list[str] — one or more reply message strings (each <= 5000 chars)
    """
    text = text.strip()

    # ── 查 <CODE> ────────────────────────────────────────────────────────────
    m = _RE_QUERY.match(text)
    if m:
        raw_code = m.group(1)
        ticker = _normalise_code(raw_code)
        result = _get_cached_radar(ticker)
        if result is None:
            return [
                f"找不到 {raw_code} 的最新雷達資料。\n"
                "請確認代號是否正確，或稍後再試。\n"
                f"（查詢範圍：台灣0050成分股）"
            ]
        from app.recommendation.formatter import format_single_stock_query
        return [format_single_stock_query(result)]

    # ── 今日雷達 ─────────────────────────────────────────────────────────────
    if _RE_TODAY_RADAR.match(text):
        summary = _get_today_cached_summary()
        if summary is None:
            today = datetime.today().strftime("%Y-%m-%d")
            return [
                f"今日（{today}）的雷達資料尚未就緒。\n"
                "分析通常在每日 14:00 CST 後更新。"
            ]
        return [summary]

    # ── 追蹤 <CODE> ──────────────────────────────────────────────────────────
    m = _RE_ADD.match(text)
    if m:
        raw_code = m.group(1)
        ticker = _normalise_code(raw_code)
        added = add_ticker(user_id, ticker)
        if added:
            return [f"✅ 已將 {ticker} 加入追蹤清單。\n輸入「我的清單」查看所有追蹤股票。"]
        else:
            return [f"ℹ️ {ticker} 已在您的追蹤清單中。"]

    # ── 移除 <CODE> ──────────────────────────────────────────────────────────
    m = _RE_REMOVE.match(text)
    if m:
        raw_code = m.group(1)
        ticker = _normalise_code(raw_code)
        removed = remove_ticker(user_id, ticker)
        if removed:
            return [f"✅ 已從追蹤清單移除 {ticker}。"]
        else:
            return [f"ℹ️ {ticker} 不在您的追蹤清單中。"]

    # ── 我的清單 ─────────────────────────────────────────────────────────────
    if _RE_WATCHLIST.match(text):
        tickers = get_watchlist(user_id)
        if not tickers:
            return [
                "您的追蹤清單目前是空的。\n"
                "輸入「追蹤 <代號>」（例：追蹤 2330）即可加入。"
            ]
        lines = ["📋 我的追蹤清單", "─" * 20]
        for i, t in enumerate(tickers, 1):
            lines.append(f"  {i}. {t}")
        lines.append("─" * 20)
        lines.append(f"共 {len(tickers)} 支\n輸入「移除 <代號>」可從清單中移除。")
        return ["\n".join(lines)]

    # ── 幫助 / help ──────────────────────────────────────────────────────────
    if _RE_HELP.match(text):
        return [HELP_TEXT]

    # ── Fallback: unknown command ─────────────────────────────────────────────
    return [
        f"指令「{text[:20]}」無法識別。\n\n{HELP_TEXT}"
    ]
