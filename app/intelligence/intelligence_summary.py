"""
app/intelligence/intelligence_summary.py — Format intelligence summaries.
"""
from __future__ import annotations

from app.intelligence.news_provider import get_market_news, get_stock_news

_NO_DATA_MSG = "目前尚未接入即時新聞事件，以下僅為技術面觀察。"


def get_daily_intelligence_text() -> str:
    """
    Return a short text summary of today's market events.
    Returns a fallback message if no data available.
    """
    events = get_market_news()
    if not events:
        return _NO_DATA_MSG

    high = [e for e in events if e.impact_level == "high"]
    if not high:
        high = events[:3]

    lines = ["📰 今日市場動態"]
    for e in high[:3]:
        icon = {"positive": "🟢", "negative": "🔴", "neutral": "⚪"}.get(e.sentiment, "⚪")
        lines.append(f"{icon} {e.headline}")
        if e.source:
            lines.append(f"   來源：{e.source}")
    return "\n".join(lines)


def get_stock_intelligence_text(ticker: str) -> str:
    """
    Return news context for a specific stock.
    Returns empty string if no relevant news.
    """
    events = get_stock_news(ticker)
    if not events:
        return ""
    lines = ["📰 相關訊息"]
    for e in events[:2]:
        icon = {"positive": "🟢", "negative": "🔴", "neutral": "⚪"}.get(e.sentiment, "⚪")
        lines.append(f"{icon} {e.headline}")
    return "\n".join(lines)
