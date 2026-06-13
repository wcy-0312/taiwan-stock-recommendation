"""
app/intelligence/news_provider.py — News provider with JSON fallback.

No live RSS scraping. Reads from data/market_events/latest.json.
If file missing or malformed, returns empty list (never raises).
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional

from app.intelligence.event_context import MarketEvent, classify_sentiment

logger = logging.getLogger(__name__)

_EVENTS_DIR = Path(__file__).parent.parent.parent / "data" / "market_events"
_LATEST_FILE = _EVENTS_DIR / "latest.json"


def _load_events() -> list[MarketEvent]:
    """Load events from data/market_events/latest.json. Returns [] on any error."""
    if not _LATEST_FILE.exists():
        return []
    try:
        with _LATEST_FILE.open(encoding="utf-8") as fh:
            raw = json.load(fh)
        events = []
        for item in raw.get("events", []):
            headline = item.get("headline", "")
            sentiment = item.get("sentiment") or classify_sentiment(headline)
            events.append(MarketEvent(
                headline=headline,
                source=item.get("source", ""),
                published_at=item.get("published_at", ""),
                related_tickers=item.get("related_tickers", []),
                sentiment=sentiment,
                impact_level=item.get("impact_level", "low"),
                url=item.get("url", ""),
            ))
        return events
    except Exception as exc:
        logger.warning("news_provider: could not load events — %s", exc)
        return []


def get_market_news() -> list[MarketEvent]:
    """Return all market events. Empty list if no data available."""
    return _load_events()


def get_stock_news(ticker: str) -> list[MarketEvent]:
    """Return events related to a specific ticker."""
    code = ticker.replace(".TW", "").upper()
    return [e for e in _load_events() if code in [t.upper() for t in e.related_tickers]]
