"""
app/config.py — Centralised configuration for 台股智能雷達 LINE Bot V2.

All settings are loaded from environment variables (via .env) or defaults.
Do NOT import from this module at function call time inside loops — read once.
"""

from __future__ import annotations

import os
from pathlib import Path

# ── Project root ──────────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).parent.parent

# ── Data paths ────────────────────────────────────────────────────────────────
UNIVERSES_DIR = PROJECT_ROOT / "data" / "universes"
CACHE_DIR = PROJECT_ROOT / "data" / "cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

WATCHLIST_DB_PATH = PROJECT_ROOT / "data" / "watchlist.db"
TW0050_UNIVERSE_PATH = UNIVERSES_DIR / "tw0050.json"

# ── LINE credentials (loaded from env) ───────────────────────────────────────
LINE_CHANNEL_ACCESS_TOKEN: str = os.getenv("LINE_CHANNEL_ACCESS_TOKEN", "")
LINE_CHANNEL_SECRET: str = os.getenv("LINE_CHANNEL_SECRET", "")
LINE_USER_ID: str = os.getenv("LINE_USER_ID", "")

# ── Data fetching ─────────────────────────────────────────────────────────────
YFINANCE_HISTORY_DAYS: int = 90       # calendar days of OHLCV history to fetch
YFINANCE_BATCH_DELAY: float = 0.3     # seconds between ticker fetches
DELISTED_TICKERS: set[str] = {"2888.TW"}  # known-delisted; skip gracefully

# ── Scheduling (CST = UTC+8) ──────────────────────────────────────────────────
ANALYSIS_HOUR_CST: int = 14
ANALYSIS_MINUTE_CST: int = 0
PUSH_HOUR_CST: int = 8
PUSH_MINUTE_CST: int = 30

# ── Scoring thresholds ────────────────────────────────────────────────────────
# Sub-score maximums
TREND_SCORE_MAX: int = 30
MOMENTUM_SCORE_MAX: int = 20
VOLUME_SCORE_MAX: int = 20
RISK_SCORE_MAX: int = 15
MARKET_SCORE_MAX: int = 10

# Direction thresholds
BULLISH_THRESHOLD: int = 70
BEARISH_THRESHOLD: int = 35

# Confidence thresholds
CONFIDENCE_HIGH_RADAR_SCORE: int = 80
CONFIDENCE_HIGH_VOLUME_RATIO: float = 1.2
CONFIDENCE_HIGH_MAX_RISK_NOTES: int = 1
CONFIDENCE_HIGH_MIN_POSITIVE_REASONS: int = 3
CONFIDENCE_MID_RADAR_SCORE: int = 60

# Selection gate uses base_score (trend+momentum+volume+risk), NOT radar_score
BASE_SCORE_STRONG_THRESHOLD: int = 70     # strong_watchlist selection gate
BASE_SCORE_WEAK_THRESHOLD: int = 35       # weakness_alerts selection gate

# Broadcast limits
STRONG_WATCHLIST_MAX: int = 5
STRONG_WATCHLIST_BROADCAST_TOP: int = 3
WEAKNESS_ALERTS_MAX: int = 5
WEAKNESS_ALERTS_BROADCAST_TOP: int = 2

# ── LINE message limits ───────────────────────────────────────────────────────
LINE_MESSAGE_MAX_CHARS: int = 5000
LINE_MESSAGE_MAX_PARTS: int = 3

# ── Web Dashboard ─────────────────────────────────────────────────────────────
PUBLIC_BASE_URL: str = os.getenv("PUBLIC_BASE_URL", "").rstrip("/")
# Set to your Render URL, e.g. https://taiwan-stock-radar-linebot.onrender.com
