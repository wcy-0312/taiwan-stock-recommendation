"""
app/intelligence/event_context.py — Market event data model.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class MarketEvent:
    headline: str
    source: str
    published_at: str           # ISO date string "YYYY-MM-DD"
    related_tickers: list[str] = field(default_factory=list)
    sentiment: str = "unknown"  # positive / neutral / negative / unknown
    impact_level: str = "low"   # high / medium / low
    url: str = ""

    def to_dict(self) -> dict:
        return {
            "headline": self.headline,
            "source": self.source,
            "published_at": self.published_at,
            "related_tickers": self.related_tickers,
            "sentiment": self.sentiment,
            "impact_level": self.impact_level,
            "url": self.url,
        }


SENTIMENT_POSITIVE_KEYWORDS = ["上漲", "突破", "利多", "強勢", "創高", "買超"]
SENTIMENT_NEGATIVE_KEYWORDS = ["下跌", "破底", "利空", "弱勢", "賣超", "跌破"]


def classify_sentiment(headline: str) -> str:
    """Keyword-based sentiment classification."""
    for kw in SENTIMENT_POSITIVE_KEYWORDS:
        if kw in headline:
            return "positive"
    for kw in SENTIMENT_NEGATIVE_KEYWORDS:
        if kw in headline:
            return "negative"
    return "neutral"
