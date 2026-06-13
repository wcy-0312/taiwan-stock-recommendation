"""
app/linebot/flex_templates.py — LINE Flex Message and Quick Reply templates.

All functions return dicts in LINE Messaging API v2 format.
Each template has a text_fallback() companion for environments that don't support Flex.

Reference: https://developers.line.biz/en/docs/messaging-api/flex-message-elements/
"""
from __future__ import annotations
from typing import Optional
import os

def _get_base_url() -> str:
    return os.environ.get("PUBLIC_BASE_URL", "").rstrip("/")


# ── Quick Reply helpers ────────────────────────────────────────────────────────

def quick_reply_item(label: str, text: str) -> dict:
    """Single Quick Reply button that sends a text message."""
    return {
        "type": "action",
        "action": {"type": "message", "label": label, "text": text}
    }

def quick_reply_url(label: str, url: str) -> dict:
    """Single Quick Reply button that opens a URL."""
    return {
        "type": "action",
        "action": {"type": "uri", "label": label, "uri": url}
    }

def quick_reply(items: list[dict]) -> dict:
    """Build a quickReply object (max 13 items)."""
    return {"items": items[:13]}

HOME_QUICK_REPLY = quick_reply([
    quick_reply_item("📊 今日雷達", "今日雷達"),
    quick_reply_item("🏆 強勢股", "強勢股"),
    quick_reply_item("⚠️ 轉弱股", "轉弱股"),
    quick_reply_item("🔍 查台積電", "查 2330"),
    quick_reply_item("📋 我的清單", "我的清單"),
    quick_reply_item("❓ 使用教學", "幫助"),
])

AFTER_QUERY_QUICK_REPLY_TEMPLATE = [
    "📊 今日雷達",
    "🏆 強勢股",
    "📋 我的清單",
]


# ── Text messages with Quick Reply ────────────────────────────────────────────

def greeting_message() -> dict:
    """Greeting message with Quick Reply buttons."""
    text = (
        "嗨，我是台股智能雷達 👋\n"
        "我可以幫你查看今日強勢股、轉弱警示，或查詢個股雷達分析。\n\n"
        "點選下面功能開始使用 ⬇️"
    )
    return {
        "type": "text",
        "text": text,
        "quickReply": HOME_QUICK_REPLY,
    }

def help_message() -> dict:
    """Help message with Quick Reply buttons."""
    text = (
        "【台股技術雷達 功能】\n"
        "─────────────────\n"
        "📊 今日雷達   — 今日播報摘要\n"
        "🏆 強勢股     — 強勢觀察清單\n"
        "⚠️ 轉弱股     — 轉弱警示清單\n"
        "🔍 查 2330   — 個股雷達分析\n"
        "📋 我的清單   — 追蹤清單\n"
        "🔖 追蹤 2330 — 加入追蹤\n"
        "🗑️ 移除 2330 — 移除追蹤\n"
        "─────────────────\n"
        "以上僅為量化技術觀察，不構成投資建議。"
    )
    return {
        "type": "text",
        "text": text,
        "quickReply": HOME_QUICK_REPLY,
    }

def unknown_command_message(user_text: str = "") -> dict:
    """Friendly unknown command response with Quick Reply."""
    preview = user_text[:15] + "…" if len(user_text) > 15 else user_text
    text = (
        f"我看不懂「{preview}」，但你可以試試：\n"
        "⬇️ 點選下方快速選單"
    ) if preview else (
        "我看不懂這句，但你可以試試：\n"
        "⬇️ 點選下方快速選單"
    )
    return {
        "type": "text",
        "text": text,
        "quickReply": HOME_QUICK_REPLY,
    }

def stock_not_found_message(code: str) -> dict:
    """Friendly 'stock not found' with guidance Quick Reply."""
    base_url = _get_base_url()
    text = (
        f"找不到 {code} 的雷達資料 🔍\n\n"
        "可能原因：\n"
        "• 目前主要追蹤 台灣 0050 成分股\n"
        "• 今日資料尚未更新（更新時間約 14:00）\n"
        "• 代號格式：請輸入 4 位數字，例：2330\n\n"
        "你可以試試："
    )
    items = [
        quick_reply_item("🏆 今日強勢股", "強勢股"),
        quick_reply_item("🔥 熱門股票", "熱門股票"),
        quick_reply_item("📋 可查股票", "可查股票"),
        quick_reply_item("📊 今日雷達", "今日雷達"),
    ]
    return {
        "type": "text",
        "text": text,
        "quickReply": quick_reply(items),
    }


# ── Flex Message templates ─────────────────────────────────────────────────────

def stock_summary_flex(result, add_watchlist_btn: bool = True) -> dict:
    """
    Flex Message bubble for a single stock query result.

    Parameters
    ----------
    result : StockRadarResult
    add_watchlist_btn : bool — whether to show 加入追蹤 button

    Returns
    -------
    dict — LINE Flex Message object (type: flex)
    """
    base_url = _get_base_url()
    code = getattr(result, "code", "")
    name = getattr(result, "name", code)
    radar_score = getattr(result, "radar_score", 0)
    direction = getattr(result, "direction", "neutral")
    confidence = getattr(result, "confidence", "低")
    close = getattr(result, "latest_close", 0)
    chg_1d = getattr(result, "price_change_1d_pct", 0)
    chg_5d = getattr(result, "price_change_5d_pct", 0)
    positive = getattr(result, "positive_reasons", [])[:2]
    risks = getattr(result, "risk_notes", [])[:1]
    trend = getattr(result, "trend_score", 0)
    momentum = getattr(result, "momentum_score", 0)
    volume = getattr(result, "volume_score", 0)
    risk_s = getattr(result, "risk_score", 0)
    market = getattr(result, "market_score", 0)

    direction_emoji = {"bullish": "🟢", "bearish": "🔴"}.get(direction, "⚪")
    chg_1d_str = f"+{chg_1d:.1f}%" if chg_1d >= 0 else f"{chg_1d:.1f}%"
    chg_5d_str = f"+{chg_5d:.1f}%" if chg_5d >= 0 else f"{chg_5d:.1f}%"

    reasons_text = "\n".join(f"✅ {r}" for r in positive) if positive else "—"
    risk_text = "\n".join(f"⚠️ {r}" for r in risks) if risks else "—"
    sub_scores = f"趨勢{trend}｜動能{momentum}｜量能{volume}｜風險{risk_s}｜市場{market}"

    body_contents = [
        {"type": "box", "layout": "horizontal", "contents": [
            {"type": "text", "text": f"{code} {name}", "weight": "bold", "size": "lg", "flex": 1},
            {"type": "text", "text": f"{direction_emoji} 雷達{radar_score}", "size": "sm", "color": "#888888", "align": "end"},
        ]},
        {"type": "separator", "margin": "md"},
        {"type": "box", "layout": "horizontal", "margin": "md", "contents": [
            {"type": "text", "text": f"收盤 {close:.2f}", "size": "sm", "flex": 1},
            {"type": "text", "text": f"日漲跌 {chg_1d_str}", "size": "sm", "flex": 1, "align": "center"},
            {"type": "text", "text": f"5日 {chg_5d_str}", "size": "sm", "flex": 1, "align": "end"},
        ]},
        {"type": "text", "text": sub_scores, "size": "xs", "color": "#888888", "margin": "sm"},
        {"type": "separator", "margin": "md"},
        {"type": "text", "text": reasons_text, "size": "sm", "wrap": True, "margin": "md"},
    ]
    if risks:
        body_contents.append({"type": "text", "text": risk_text, "size": "sm", "wrap": True, "margin": "sm", "color": "#FF6B6B"})

    footer_contents = []
    if add_watchlist_btn:
        footer_contents.append({
            "type": "button", "style": "primary", "height": "sm",
            "action": {"type": "message", "label": f"追蹤 {code}", "text": f"追蹤 {code}"},
        })
    if base_url:
        footer_contents.append({
            "type": "button", "style": "secondary", "height": "sm", "margin": "sm",
            "action": {"type": "uri", "label": "完整分析", "uri": f"{base_url}/stock/{code}"},
        })

    bubble = {
        "type": "bubble",
        "body": {"type": "box", "layout": "vertical", "contents": body_contents},
    }
    if footer_contents:
        bubble["footer"] = {"type": "box", "layout": "vertical", "contents": footer_contents}

    return {"type": "flex", "altText": f"{code} {name} 雷達分析", "contents": bubble}


def watchlist_flex(tickers: list[str], results: dict) -> dict:
    """
    Flex Message carousel for a user's watchlist.

    Parameters
    ----------
    tickers : list[str] — list of ticker strings (e.g. ["2330.TW"])
    results : dict — ticker -> StockRadarResult (may be partial)

    Returns
    -------
    dict — LINE Flex Message carousel or text fallback
    """
    if not tickers:
        return {"type": "text", "text": "您的追蹤清單是空的。\n輸入「追蹤 2330」可加入。"}

    base_url = _get_base_url()
    bubbles = []
    for ticker in tickers[:10]:
        code = ticker.replace(".TW", "")
        r = results.get(ticker)
        if r:
            direction_emoji = {"bullish": "🟢", "bearish": "🔴"}.get(getattr(r, "direction", ""), "⚪")
            score = getattr(r, "radar_score", 0)
            conf = getattr(r, "confidence", "低")
            name = getattr(r, "name", code)
            body_text = f"{direction_emoji} 雷達:{score} 信心:{conf}"
        else:
            name = code
            body_text = "今日資料未更新"

        footer = []
        if base_url:
            footer.append({"type": "button", "style": "secondary", "height": "sm",
                "action": {"type": "uri", "label": "查看", "uri": f"{base_url}/stock/{code}"}})
        footer.append({"type": "button", "style": "secondary", "height": "sm", "margin": "sm",
            "action": {"type": "message", "label": "移除", "text": f"移除 {code}"}})

        bubbles.append({
            "type": "bubble", "size": "micro",
            "header": {"type": "box", "layout": "vertical", "contents": [
                {"type": "text", "text": f"{code} {name}", "weight": "bold", "size": "sm"},
            ]},
            "body": {"type": "box", "layout": "vertical", "contents": [
                {"type": "text", "text": body_text, "size": "xs", "wrap": True},
            ]},
            "footer": {"type": "box", "layout": "vertical", "contents": footer},
        })

    return {
        "type": "flex",
        "altText": f"我的追蹤清單（{len(tickers)} 支）",
        "contents": {"type": "carousel", "contents": bubbles},
    }


def daily_radar_flex(market_stats: dict, strong: list, weak: list) -> dict:
    """
    Flex Message for daily radar broadcast summary.

    Parameters
    ----------
    market_stats : dict — bullish_count, universe_size, market_score
    strong : list — top 3 StockRadarResult bullish
    weak   : list — top 2 StockRadarResult bearish

    Returns
    -------
    dict — LINE Flex Message object
    """
    base_url = _get_base_url()
    bull_count = market_stats.get("bullish_count", 0)
    universe_size = market_stats.get("universe_size", 50)
    mkt_score = market_stats.get("market_score", 5)

    body_contents = [
        {"type": "text", "text": "📊 台股技術雷達", "weight": "bold", "size": "xl"},
        {"type": "text", "text": f"市場：{bull_count}/{universe_size} 偏多｜市場分 {mkt_score}/10",
         "size": "sm", "color": "#888888"},
        {"type": "separator", "margin": "md"},
    ]

    if strong:
        body_contents.append({"type": "text", "text": "🏆 強勢觀察", "weight": "bold", "size": "sm", "margin": "md"})
        for i, r in enumerate(strong[:3], 1):
            code = getattr(r, "code", "")
            name = getattr(r, "name", code)
            score = getattr(r, "radar_score", 0)
            body_contents.append({
                "type": "text", "text": f"#{i} {code} {name}  雷達{score}",
                "size": "sm", "action": {"type": "message", "label": code, "text": f"查 {code}"}
            })

    if weak:
        body_contents.append({"type": "text", "text": "⚠️ 轉弱警示", "weight": "bold", "size": "sm", "margin": "md"})
        for i, r in enumerate(weak[:2], 1):
            code = getattr(r, "code", "")
            name = getattr(r, "name", code)
            score = getattr(r, "radar_score", 0)
            body_contents.append({
                "type": "text", "text": f"#{i} {code} {name}  雷達{score}", "size": "sm"
            })

    footer_contents = [
        {"type": "button", "style": "primary", "height": "sm",
         "action": {"type": "message", "label": "強勢股 Top 10", "text": "強勢股"}},
        {"type": "button", "style": "secondary", "height": "sm", "margin": "sm",
         "action": {"type": "message", "label": "轉弱警示", "text": "轉弱股"}},
    ]
    if base_url:
        footer_contents.append({
            "type": "button", "style": "secondary", "height": "sm", "margin": "sm",
            "action": {"type": "uri", "label": "完整看板", "uri": f"{base_url}/dashboard"},
        })

    bubble = {
        "type": "bubble",
        "body": {"type": "box", "layout": "vertical", "contents": body_contents},
        "footer": {"type": "box", "layout": "vertical", "contents": footer_contents},
    }
    return {"type": "flex", "altText": "台股技術雷達 今日播報", "contents": bubble}


# ── Hot stocks list ────────────────────────────────────────────────────────────

HOT_STOCKS = [
    ("2330", "台積電"),
    ("2317", "鴻海"),
    ("2454", "聯發科"),
    ("2884", "玉山金"),
    ("2891", "中信金"),
]

def hot_stocks_message() -> dict:
    """Return hot stocks with Quick Reply for each."""
    items = [quick_reply_item(f"🔍 {code} {name}", f"查 {code}") for code, name in HOT_STOCKS]
    items.append(quick_reply_item("📋 可查股票", "可查股票"))
    return {
        "type": "text",
        "text": "🔥 熱門股票快速查詢：",
        "quickReply": quick_reply(items),
    }
