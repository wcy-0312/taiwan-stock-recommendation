"""
app/linebot/commands.py — Parse and dispatch LINE Bot interactive commands.

V4 changes:
  - Uses app.cache.latest_cache (holiday-safe cache module)
  - New 新聞 / 市場新聞 / 市場事件 command (WS-2D)
  - Unknown command text updated (WS-4F1)
  - Hot stocks updated with 2412/2891 (WS-4F2)
  - 我的清單 now uses find_stock_in_latest_cache (WS-4F3)

Supported commands (case-insensitive, leading/trailing whitespace ignored):

    查 <CODE>                    — Query latest radar result for a stock code
    <4-digit>                    — Bare 4-digit number treated as alias for 查 <CODE>
    今日雷達                       — Return today's broadcast summary from cache
    強勢股                         — Top 5 bullish stocks from latest cache
    轉弱股                         — Top 5 bearish stocks from latest cache
    熱門股票                       — Hot stocks quick-access menu
    可查股票                       — List first 20 tickers in the universe
    新聞 / 市場新聞 / 市場事件      — Latest market events Flex Message
    追蹤 <CODE>                   — Add a stock to the user's watchlist
    移除 <CODE>                   — Remove a stock from the user's watchlist
    我的清單                       — List the user's watchlist (with radar data)
    幫助 / help                    — Return the help text
    你好 / 嗨 / hi                 — Greeting

Unknown messages return a friendly prompt with Quick Reply.

dispatch_command() returns list[dict] — each element is a LINE message object
(type: text, flex, etc.) ready to be passed directly to the Messaging API.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime
from typing import Optional

from app.linebot.watchlist import add_ticker, remove_ticker, get_watchlist
from app.linebot.flex_templates import (
    greeting_message,
    help_message,
    unknown_command_message,
    stock_not_found_message,
    hot_stocks_message,
    HOME_QUICK_REPLY,
    quick_reply,
    quick_reply_item,
    stock_summary_flex,
    watchlist_flex,
    news_flex,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Command patterns
# ---------------------------------------------------------------------------

_RE_QUERY = re.compile(r"^查\s+([A-Za-z0-9]+\.?[A-Za-z]*)$", re.UNICODE)
_RE_BARE_CODE = re.compile(r"^\d{4}$", re.UNICODE)          # bare 4-digit: "2330"
_RE_ADD = re.compile(r"^追蹤\s+([A-Za-z0-9]+\.?[A-Za-z]*)$", re.UNICODE)
_RE_REMOVE = re.compile(r"^移除\s+([A-Za-z0-9]+\.?[A-Za-z]*)$", re.UNICODE)
_RE_WATCHLIST = re.compile(r"^我的清單$", re.UNICODE)
_RE_TODAY_RADAR = re.compile(r"^今日雷達$", re.UNICODE)
_RE_STRONG = re.compile(r"^強勢股$", re.UNICODE)
_RE_WEAK = re.compile(r"^轉弱股$", re.UNICODE)
_RE_HOT = re.compile(r"^熱門股票$", re.UNICODE)
_RE_LIST_UNIVERSE = re.compile(r"^可查股票$", re.UNICODE)
_RE_NEWS = re.compile(r"^(新聞|市場新聞|市場事件)$", re.UNICODE)
_RE_HELP = re.compile(r"^(幫助|help|Help|HELP|功能|怎麼用)$", re.UNICODE)
_RE_GREET = re.compile(r"^(你好|嗨|hi|hello|哈囉|Hello|HI|HELLO)$", re.UNICODE | re.IGNORECASE)


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


def _text_msg(text: str, quick_reply_obj: Optional[dict] = None) -> dict:
    """Build a plain text LINE message object, optionally with a quickReply."""
    msg: dict = {"type": "text", "text": text}
    if quick_reply_obj:
        msg["quickReply"] = quick_reply_obj
    return msg


# ---------------------------------------------------------------------------
# Cache helpers (V4: use latest_cache module)
# ---------------------------------------------------------------------------

def _get_cached_radar(ticker: str) -> Optional[object]:
    """
    Try to load the most recent cached analysis result for a ticker.
    Uses find_stock_in_latest_cache (holiday-safe).
    Returns a StockRadarResult-like object or None if not found.
    """
    try:
        from app.cache.latest_cache import find_stock_in_latest_cache
        from app.scoring.models import StockRadarResult

        r = find_stock_in_latest_cache(ticker)
        if r is None:
            return None

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
    Load broadcast summary from the most recent cache (holiday-safe).
    Returns a formatted string or None.
    """
    try:
        from app.cache.latest_cache import load_latest_analysis_cache, get_latest_analysis_date

        data = load_latest_analysis_cache()
        if data is None:
            return None

        data_date = get_latest_analysis_date()
        market_stats = data.get("market_stats", {})
        results_raw = data.get("results", [])

        bull_count = int(market_stats.get("bullish_count") or 0)
        universe_size = int(market_stats.get("universe_size") or len(results_raw))
        mkt_score = int(market_stats.get("market_score") or 5)

        strong = [r for r in results_raw if r.get("direction") == "bullish"][:3]
        weak = [r for r in results_raw if r.get("direction") == "bearish"][:2]

        lines = [
            f"📊 台股智能雷達 {data_date}",
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

        # Show data date label if not today (holiday indicator)
        from datetime import date as _date
        today_str = _date.today().isoformat()
        if data_date != today_str and data_date != "—":
            lines.append(f"資料日期: {data_date} 收盤")

        lines.append("以上僅為量化技術觀察，不構成投資建議。")
        return "\n".join(lines)
    except Exception as exc:
        logger.warning("_get_today_cached_summary: error — %s", exc)
        return None


def _has_recent_cache() -> bool:
    """Return True if any analysis cache file exists."""
    try:
        from app.config import CACHE_DIR
        return any(CACHE_DIR.glob("analysis_*.json"))
    except Exception:
        return False


def _get_strong_stocks(top_n: int = 5) -> list[dict]:
    """Return top N bullish stocks from the most recent cache file."""
    try:
        from app.cache.latest_cache import list_latest_results
        results = list_latest_results()
        bullish = [r for r in results if r.get("direction") == "bullish"]
        bullish.sort(key=lambda r: int(r.get("radar_score") or 0), reverse=True)
        return bullish[:top_n]
    except Exception as exc:
        logger.warning("_get_strong_stocks: error — %s", exc)
    return []


def _get_weak_stocks(top_n: int = 5) -> list[dict]:
    """Return top N bearish stocks from the most recent cache file."""
    try:
        from app.cache.latest_cache import list_latest_results
        results = list_latest_results()
        bearish = [r for r in results if r.get("direction") == "bearish"]
        bearish.sort(key=lambda r: int(r.get("radar_score") or 0))
        return bearish[:top_n]
    except Exception as exc:
        logger.warning("_get_weak_stocks: error — %s", exc)
    return []


def _load_universe_tickers() -> list[str]:
    """
    Load ticker codes from the TW0050 universe file.
    Returns a list of bare codes (without .TW suffix) sorted alphabetically.
    """
    try:
        from app.config import TW0050_UNIVERSE_PATH
        with TW0050_UNIVERSE_PATH.open(encoding="utf-8") as fh:
            data = json.load(fh)
        if isinstance(data, list):
            tickers = []
            for item in data:
                if isinstance(item, str):
                    tickers.append(item.replace(".TW", "").strip())
                elif isinstance(item, dict):
                    code = item.get("code") or item.get("ticker", "")
                    tickers.append(code.replace(".TW", "").strip())
            return [t for t in tickers if t]
        elif isinstance(data, dict):
            raw = data.get("tickers", data.get("stocks", []))
            tickers = []
            for item in raw:
                if isinstance(item, str):
                    tickers.append(item.replace(".TW", "").strip())
                elif isinstance(item, dict):
                    code = item.get("code") or item.get("ticker", "")
                    tickers.append(code.replace(".TW", "").strip())
            return [t for t in tickers if t]
    except Exception as exc:
        logger.warning("_load_universe_tickers: could not load universe — %s", exc)
    return []


def _load_market_events() -> list[dict]:
    """Load market events from data/market_events/latest.json."""
    try:
        from pathlib import Path
        events_path = Path(__file__).parent.parent.parent / "data" / "market_events" / "latest.json"
        if not events_path.exists():
            return []
        with events_path.open(encoding="utf-8") as fh:
            data = json.load(fh)
        return data.get("events", [])
    except Exception as exc:
        logger.warning("_load_market_events: %s", exc)
    return []


# ---------------------------------------------------------------------------
# Command dispatcher
# ---------------------------------------------------------------------------

def dispatch_command(user_id: str, text: str) -> list[dict]:
    """
    Parse a LINE message text and return a list of LINE message objects.

    Parameters
    ----------
    user_id : str — LINE user_id of the sender (for watchlist operations)
    text    : str — raw message text from the LINE webhook event

    Returns
    -------
    list[dict] — one or more LINE message dicts (type: text / flex / etc.)
                 Each dict is ready to be sent as-is via the Messaging API.
    """
    text = text.strip()

    # ── Greeting ─────────────────────────────────────────────────────────────
    if _RE_GREET.match(text):
        return [greeting_message()]

    # ── 幫助 / help ──────────────────────────────────────────────────────────
    if _RE_HELP.match(text):
        return [help_message()]

    # ── 查 <CODE> ────────────────────────────────────────────────────────────
    m = _RE_QUERY.match(text)
    if m:
        raw_code = m.group(1)
        return _handle_stock_query(raw_code)

    # ── Bare 4-digit code (e.g. "2330" → alias for "查 2330") ───────────────
    if _RE_BARE_CODE.match(text):
        return _handle_stock_query(text)

    # ── 今日雷達 ─────────────────────────────────────────────────────────────
    if _RE_TODAY_RADAR.match(text):
        summary = _get_today_cached_summary()
        if summary is None:
            today = datetime.today().strftime("%Y-%m-%d")
            return [_text_msg(
                f"今日（{today}）的雷達資料尚未就緒。\n"
                "分析通常在每日 14:00 CST 後更新。",
                HOME_QUICK_REPLY,
            )]
        return [_text_msg(summary, HOME_QUICK_REPLY)]

    # ── 強勢股 ───────────────────────────────────────────────────────────────
    if _RE_STRONG.match(text):
        return _handle_strong_stocks()

    # ── 轉弱股 ───────────────────────────────────────────────────────────────
    if _RE_WEAK.match(text):
        return _handle_weak_stocks()

    # ── 熱門股票 ─────────────────────────────────────────────────────────────
    if _RE_HOT.match(text):
        return [hot_stocks_message()]

    # ── 可查股票 ─────────────────────────────────────────────────────────────
    if _RE_LIST_UNIVERSE.match(text):
        return _handle_list_universe()

    # ── 新聞 / 市場新聞 / 市場事件 ──────────────────────────────────────────
    if _RE_NEWS.match(text):
        return _handle_news()

    # ── 追蹤 <CODE> ──────────────────────────────────────────────────────────
    m = _RE_ADD.match(text)
    if m:
        raw_code = m.group(1)
        ticker = _normalise_code(raw_code)
        added = add_ticker(user_id, ticker)
        if added:
            return [_text_msg(
                f"✅ 已將 {ticker} 加入追蹤清單。\n輸入「我的清單」查看所有追蹤股票。",
                HOME_QUICK_REPLY,
            )]
        else:
            return [_text_msg(
                f"ℹ️ {ticker} 已在您的追蹤清單中。",
                HOME_QUICK_REPLY,
            )]

    # ── 移除 <CODE> ──────────────────────────────────────────────────────────
    m = _RE_REMOVE.match(text)
    if m:
        raw_code = m.group(1)
        ticker = _normalise_code(raw_code)
        removed = remove_ticker(user_id, ticker)
        if removed:
            return [_text_msg(
                f"✅ 已從追蹤清單移除 {ticker}。",
                HOME_QUICK_REPLY,
            )]
        else:
            return [_text_msg(
                f"ℹ️ {ticker} 不在您的追蹤清單中。",
                HOME_QUICK_REPLY,
            )]

    # ── 我的清單 ─────────────────────────────────────────────────────────────
    if _RE_WATCHLIST.match(text):
        return _handle_watchlist(user_id)

    # ── Fallback: unknown command ─────────────────────────────────────────────
    return [unknown_command_message(text)]


# ---------------------------------------------------------------------------
# Sub-handlers (keep dispatch_command readable)
# ---------------------------------------------------------------------------

def _handle_stock_query(raw_code: str) -> list[dict]:
    """Handle 查 <CODE> and bare 4-digit lookups."""
    ticker = _normalise_code(raw_code)
    result = _get_cached_radar(ticker)
    if result is None:
        return [stock_not_found_message(raw_code.upper())]

    # Build after-query Quick Reply
    code = getattr(result, "code", raw_code.upper())
    after_qr = quick_reply([
        quick_reply_item("📊 今日雷達", "今日雷達"),
        quick_reply_item("🏆 強勢股", "強勢股"),
        quick_reply_item("📋 我的清單", "我的清單"),
        quick_reply_item(f"🔖 追蹤 {code}", f"追蹤 {code}"),
    ])
    flex = stock_summary_flex(result, add_watchlist_btn=True)
    flex["quickReply"] = after_qr
    return [flex]


def _handle_strong_stocks() -> list[dict]:
    """Return top 5 bullish stocks text + Quick Reply to query each."""
    stocks = _get_strong_stocks(top_n=5)
    if not stocks:
        today = datetime.today().strftime("%Y-%m-%d")
        if _has_recent_cache():
            msg = f"今日（{today}）市場整體偏弱，目前無強勢股。\n可查看轉弱警示或等待市場回溫。"
        else:
            msg = f"今日（{today}）分析尚未完成，請稍後再試。\n分析通常在每日 14:00 CST 後更新。"
        return [_text_msg(msg, HOME_QUICK_REPLY)]

    lines = ["🏆 強勢股 Top 5", "─" * 20]
    qr_items = []
    for i, r in enumerate(stocks, 1):
        code = r.get("code", "")
        name = r.get("name", code)
        rs = int(r.get("radar_score") or 0)
        conf = r.get("confidence", "低")
        lines.append(f"#{i} {code} {name}  雷達:{rs}  信心:{conf}")
        if code:
            qr_items.append(quick_reply_item(f"🔍 {code}", f"查 {code}"))
    lines.append("─" * 20)
    lines.append("以上僅為量化技術觀察，不構成投資建議。")

    qr_items.append(quick_reply_item("⚠️ 轉弱股", "轉弱股"))
    qr_items.append(quick_reply_item("📊 今日雷達", "今日雷達"))

    return [_text_msg("\n".join(lines), quick_reply(qr_items))]


def _handle_weak_stocks() -> list[dict]:
    """Return top 5 bearish stocks text + Quick Reply to query each."""
    stocks = _get_weak_stocks(top_n=5)
    if not stocks:
        today = datetime.today().strftime("%Y-%m-%d")
        if _has_recent_cache():
            msg = f"今日（{today}）市場整體偏強，目前無轉弱警示。"
        else:
            msg = f"今日（{today}）分析尚未完成，請稍後再試。\n分析通常在每日 14:00 CST 後更新。"
        return [_text_msg(msg, HOME_QUICK_REPLY)]

    lines = ["⚠️ 轉弱股 Top 5", "─" * 20]
    qr_items = []
    for i, r in enumerate(stocks, 1):
        code = r.get("code", "")
        name = r.get("name", code)
        rs = int(r.get("radar_score") or 0)
        lines.append(f"#{i} {code} {name}  雷達:{rs}")
        if code:
            qr_items.append(quick_reply_item(f"🔍 {code}", f"查 {code}"))
    lines.append("─" * 20)
    lines.append("以上僅為量化技術觀察，不構成投資建議。")

    qr_items.append(quick_reply_item("🏆 強勢股", "強勢股"))
    qr_items.append(quick_reply_item("📊 今日雷達", "今日雷達"))

    return [_text_msg("\n".join(lines), quick_reply(qr_items))]


def _handle_news() -> list[dict]:
    """Handle 新聞 / 市場新聞 / 市場事件 command (WS-2D)."""
    events = _load_market_events()
    if not events:
        return [_text_msg(
            "目前無市場事件資訊，請稍後再試。",
            HOME_QUICK_REPLY,
        )]
    flex = news_flex(events[:5])
    flex["quickReply"] = HOME_QUICK_REPLY
    return [flex]


def _handle_watchlist(user_id: str) -> list[dict]:
    """Handle 我的清單 — show watchlist Flex + personalized web link (token-based)."""
    tickers = get_watchlist(user_id)
    if not tickers:
        return [_text_msg(
            "您的追蹤清單目前是空的。\n"
            "輸入「追蹤 <代號>」（例：追蹤 2330）即可加入。",
            HOME_QUICK_REPLY,
        )]

    # Fetch cached radar data for each ticker
    results: dict = {}
    for ticker in tickers:
        r = _get_cached_radar(ticker)
        if r is not None:
            results[ticker] = r

    msgs: list[dict] = []

    if results:
        flex = watchlist_flex(tickers, results)
        msgs.append(flex)
    else:
        lines = ["📋 我的追蹤清單", "─" * 20]
        for i, t in enumerate(tickers, 1):
            lines.append(f"  {i}. {t}")
        lines.append("─" * 20)
        lines.append(f"共 {len(tickers)} 支")
        msgs.append(_text_msg("\n".join(lines)))

    # Append a personalized web link when PUBLIC_BASE_URL is configured
    from app.config import PUBLIC_BASE_URL
    if PUBLIC_BASE_URL:
        from app.tokens import create_token
        token = create_token(user_id)
        link = f"{PUBLIC_BASE_URL}/watchlist?token={token}"
        link_bubble = {
            "type": "flex",
            "altText": "開啟追蹤清單完整頁面",
            "contents": {
                "type": "bubble", "size": "kilo",
                "body": {"type": "box", "layout": "vertical", "contents": [
                    {"type": "text", "text": "📋 完整追蹤清單", "weight": "bold", "size": "md"},
                    {"type": "text", "text": "在瀏覽器中查看完整雷達資料", "size": "xs",
                     "color": "#888888", "margin": "sm"},
                    {"type": "text", "text": "⏰ 連結 30 分鐘內有效", "size": "xs",
                     "color": "#aaaaaa", "margin": "xs"},
                ]},
                "footer": {"type": "box", "layout": "vertical", "contents": [
                    {"type": "button", "style": "primary", "height": "sm",
                     "action": {"type": "uri", "label": "開啟追蹤清單", "uri": link}},
                ]},
            },
        }
        link_bubble["quickReply"] = HOME_QUICK_REPLY
        msgs.append(link_bubble)
    else:
        msgs[-1]["quickReply"] = HOME_QUICK_REPLY

    return msgs


def _handle_list_universe() -> list[dict]:
    """Handle 可查股票 — list first 20 tickers with Quick Reply for each."""
    tickers = _load_universe_tickers()
    if not tickers:
        return [_text_msg(
            "目前無法取得可查股票清單，請稍後再試。",
            HOME_QUICK_REPLY,
        )]

    display = tickers[:20]
    lines = [f"📋 可查股票（共 {len(tickers)} 支，顯示前 20）", "─" * 20]
    for t in display:
        lines.append(f"  {t}")
    lines.append("─" * 20)
    lines.append("輸入「查 <代號>」或直接輸入 4 位數代號查詢個股。")

    qr_items = [quick_reply_item(f"🔍 {t}", f"查 {t}") for t in display[:11]]
    qr_items.append(quick_reply_item("📊 今日雷達", "今日雷達"))

    return [_text_msg("\n".join(lines), quick_reply(qr_items))]
