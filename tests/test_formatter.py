"""
tests/test_formatter.py — Unit tests for the LINE message formatter.

Tests:
    - No None or nan in any formatted output
    - Messages stay within LINE_MESSAGE_MAX_CHARS (5000)
    - Messages split into at most LINE_MESSAGE_MAX_PARTS (3)
    - _safe_float / _fmt_price / _fmt_pct handle None, NaN, Inf
    - format_stock_block never contains the string "None" or "nan"
    - format_weak_stock_block never contains "None" or "nan"
    - build_broadcast_messages returns correct structure
    - format_single_stock_query returns single string <= 5000 chars
    - Long messages are truncated with ellipsis, not left oversized
    - Strong stock with no weak stocks produces 2 messages (msg1 + msg3)
    - Zero strong, zero weak stocks produces "今日無明確技術面強勢股"
"""

from __future__ import annotations

import math
import sys
from pathlib import Path
from typing import Optional

import pytest

_PROJECT_ROOT = Path(__file__).parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from app.scoring.models import StockRadarResult
from app.recommendation.formatter import (
    build_broadcast_messages,
    format_stock_block,
    format_weak_stock_block,
    format_single_stock_query,
    _safe_float,
    _fmt_price,
    _fmt_pct,
    _fmt_score,
    _safe_str,
    _truncate,
)
from app.config import LINE_MESSAGE_MAX_CHARS, LINE_MESSAGE_MAX_PARTS


# ══════════════════════════════════════════════════════════════════════════════
# Fixtures
# ══════════════════════════════════════════════════════════════════════════════

def make_result(
    ticker: str = "2330.TW",
    code: str = "2330",
    name: str = "台積電",
    radar_score: int = 78,
    direction: str = "bullish",
    confidence: str = "中",
    latest_close: float = 900.0,
    price_change_1d_pct: float = 1.5,
    price_change_5d_pct: float = 3.0,
    trend_score: int = 22,
    momentum_score: int = 16,
    volume_score: int = 15,
    risk_score: int = 12,
    market_score: int = 8,
    ma5: float = 895.0,
    ma20: float = 880.0,
    ma60: Optional[float] = 860.0,
    rsi14: float = 62.0,
    macd_hist: float = 0.3,
    macd_hist_delta: float = 0.1,
    volume_ratio: float = 1.3,
    atr14: float = 14.0,
    atr_pct: float = 1.6,
    support_20d: float = 870.0,
    resistance_20d: float = 920.0,
    positive_reasons: list | None = None,
    negative_reasons: list | None = None,
    risk_notes: list | None = None,
    invalidation_conditions: list | None = None,
) -> StockRadarResult:
    return StockRadarResult(
        ticker=ticker, code=code, name=name,
        data_date="2026-06-13",
        latest_close=latest_close,
        price_change_1d_pct=price_change_1d_pct,
        price_change_5d_pct=price_change_5d_pct,
        radar_score=radar_score,
        rank_in_universe=1, universe_size=50,
        direction=direction, confidence=confidence,
        trend_score=trend_score, momentum_score=momentum_score,
        volume_score=volume_score, risk_score=risk_score,
        market_score=market_score, chip_score=None,
        ma5=ma5, ma20=ma20, ma60=ma60,
        rsi14=rsi14, macd_hist=macd_hist, macd_hist_delta=macd_hist_delta,
        volume_ratio=volume_ratio, atr14=atr14, atr_pct=atr_pct,
        support_20d=support_20d, resistance_20d=resistance_20d,
        positive_reasons=positive_reasons or ["多頭排列", "MACD擴大", "RSI健康"],
        negative_reasons=negative_reasons or [],
        risk_notes=risk_notes or [],
        invalidation_conditions=invalidation_conditions or ["跌破MA20則失效"],
    )


def make_weak_result() -> StockRadarResult:
    return make_result(
        code="2303", name="聯電",
        radar_score=28,
        direction="bearish",
        confidence="低",
        price_change_1d_pct=-2.5,
        trend_score=5, momentum_score=4, volume_score=8, risk_score=5, market_score=3,
        positive_reasons=[],
        negative_reasons=["空頭排列", "MACD轉負"],
        risk_notes=["ATR偏高"],
    )


# ══════════════════════════════════════════════════════════════════════════════
# 1. Safe value helpers
# ══════════════════════════════════════════════════════════════════════════════

class TestSafeHelpers:
    def test_safe_float_none(self):
        assert _safe_float(None) == 0.0

    def test_safe_float_nan(self):
        assert _safe_float(float("nan")) == 0.0

    def test_safe_float_inf(self):
        assert _safe_float(float("inf")) == 0.0
        assert _safe_float(float("-inf")) == 0.0

    def test_safe_float_valid(self):
        assert _safe_float(3.14) == pytest.approx(3.14)

    def test_safe_float_custom_fallback(self):
        assert _safe_float(None, fallback=99.0) == 99.0

    def test_fmt_price_none(self):
        result = _fmt_price(None)
        assert "None" not in result
        assert "nan" not in result.lower()
        assert "." in result  # formatted as decimal

    def test_fmt_price_nan(self):
        result = _fmt_price(float("nan"))
        assert "nan" not in result.lower()

    def test_fmt_pct_none(self):
        result = _fmt_pct(None)
        assert "None" not in result
        assert "nan" not in result.lower()
        assert "%" in result

    def test_fmt_pct_nan(self):
        result = _fmt_pct(float("nan"))
        assert "nan" not in result.lower()

    def test_fmt_score_none(self):
        result = _fmt_score(None)
        assert result == "0"

    def test_safe_str_none(self):
        assert _safe_str(None) == "—"

    def test_safe_str_empty(self):
        assert _safe_str("") == "—"

    def test_truncate_short_string(self):
        s = "hello"
        assert _truncate(s, 100) == s

    def test_truncate_long_string(self):
        s = "x" * 6000
        result = _truncate(s, 5000)
        assert len(result) == 5000
        assert result.endswith("...")


# ══════════════════════════════════════════════════════════════════════════════
# 2. format_stock_block — no None/nan
# ══════════════════════════════════════════════════════════════════════════════

class TestFormatStockBlock:
    def test_no_none_in_output(self):
        result = make_result()
        text = format_stock_block(result, rank=1)
        assert "None" not in text, f"Found 'None' in output: {text}"

    def test_no_nan_in_output(self):
        result = make_result()
        text = format_stock_block(result, rank=1)
        assert "nan" not in text.lower(), f"Found 'nan' in output: {text}"

    def test_length_within_limit(self):
        result = make_result(
            positive_reasons=["a" * 100, "b" * 100, "c" * 100],
            risk_notes=["r" * 100],
        )
        text = format_stock_block(result, rank=1)
        assert len(text) <= LINE_MESSAGE_MAX_CHARS, "format_stock_block exceeded limit"

    def test_with_none_ma60(self):
        result = make_result(ma60=None)
        text = format_stock_block(result, rank=1)
        assert "None" not in text
        assert "nan" not in text.lower()

    def test_with_none_optional_fields(self):
        """All Optional fields None → no None/nan in output."""
        result = StockRadarResult(
            ticker="X.TW", code="X", name="Test",
            data_date="2026-06-13",
            latest_close=100.0,
            price_change_1d_pct=0.0,
            price_change_5d_pct=0.0,
            radar_score=50,
            rank_in_universe=5, universe_size=50,
            direction="neutral", confidence="低",
            trend_score=10, momentum_score=8, volume_score=10, risk_score=8, market_score=5,
            chip_score=None,
            ma5=100.0, ma20=98.0, ma60=None,
            rsi14=50.0, macd_hist=0.0, macd_hist_delta=0.0,
            volume_ratio=1.0, atr14=2.0, atr_pct=2.0,
            support_20d=95.0, resistance_20d=105.0,
            positive_reasons=[], negative_reasons=[], risk_notes=[], invalidation_conditions=[],
        )
        text = format_stock_block(result, rank=3)
        assert "None" not in text
        assert "nan" not in text.lower()

    def test_with_zero_floats(self):
        """Zero float values → no None/nan in output."""
        result = make_result(
            latest_close=0.0, ma5=0.0, ma20=0.0, ma60=0.0,
            rsi14=0.0, macd_hist=0.0, volume_ratio=0.0,
        )
        text = format_stock_block(result, rank=2)
        assert "None" not in text
        assert "nan" not in text.lower()


# ══════════════════════════════════════════════════════════════════════════════
# 3. format_weak_stock_block — no None/nan
# ══════════════════════════════════════════════════════════════════════════════

class TestFormatWeakStockBlock:
    def test_no_none_in_output(self):
        result = make_weak_result()
        text = format_weak_stock_block(result, rank=1)
        assert "None" not in text
        assert "nan" not in text.lower()

    def test_length_within_limit(self):
        result = make_weak_result()
        text = format_weak_stock_block(result, rank=1)
        assert len(text) <= LINE_MESSAGE_MAX_CHARS


# ══════════════════════════════════════════════════════════════════════════════
# 4. build_broadcast_messages
# ══════════════════════════════════════════════════════════════════════════════

class TestBuildBroadcastMessages:
    def test_returns_list(self):
        msgs = build_broadcast_messages(
            strong_stocks=[make_result()],
            weak_stocks=[],
            market_stats={"bullish_count": 10, "universe_size": 50, "bullish_ratio": 0.2, "avg_base_score": 55.0, "market_score": 6},
            data_date="2026-06-13",
        )
        assert isinstance(msgs, list)

    def test_max_parts(self):
        """Must return at most LINE_MESSAGE_MAX_PARTS messages."""
        msgs = build_broadcast_messages(
            strong_stocks=[make_result(), make_result(code="2317", name="鴻海"), make_result(code="2454", name="聯發科")],
            weak_stocks=[make_weak_result(), make_weak_result()],
            market_stats={"bullish_count": 15, "universe_size": 50, "bullish_ratio": 0.3, "avg_base_score": 58.0, "market_score": 6},
            data_date="2026-06-13",
        )
        assert len(msgs) <= LINE_MESSAGE_MAX_PARTS

    def test_each_message_within_limit(self):
        """Every message must be <= 5000 chars."""
        msgs = build_broadcast_messages(
            strong_stocks=[make_result() for _ in range(3)],
            weak_stocks=[make_weak_result() for _ in range(2)],
            market_stats={"bullish_count": 10, "universe_size": 50, "bullish_ratio": 0.2, "avg_base_score": 55.0, "market_score": 5},
            data_date="2026-06-13",
        )
        for i, msg in enumerate(msgs):
            assert len(msg) <= LINE_MESSAGE_MAX_CHARS, f"Message {i+1} exceeds char limit: {len(msg)}"

    def test_no_none_nan_in_any_message(self):
        """No None or nan in any broadcast message."""
        msgs = build_broadcast_messages(
            strong_stocks=[make_result()],
            weak_stocks=[make_weak_result()],
            market_stats={"bullish_count": 5, "universe_size": 50, "bullish_ratio": 0.1, "avg_base_score": 50.0, "market_score": 4},
            data_date="2026-06-13",
        )
        for i, msg in enumerate(msgs):
            assert "None" not in msg, f"Message {i+1} contains 'None'"
            assert "nan" not in msg.lower(), f"Message {i+1} contains 'nan'"

    def test_zero_strong_shows_no_strong_text(self):
        """Zero strong stocks → 今日無明確技術面強勢股 appears."""
        msgs = build_broadcast_messages(
            strong_stocks=[],
            weak_stocks=[],
            market_stats=None,
            data_date="2026-06-13",
        )
        assert len(msgs) >= 1
        assert "今日無明確技術面強勢股" in msgs[0]

    def test_no_weak_stocks_skips_msg2(self):
        """If no weak stocks, message 2 (weakness alert) is not produced."""
        msgs = build_broadcast_messages(
            strong_stocks=[make_result()],
            weak_stocks=[],
            market_stats={"bullish_count": 8, "universe_size": 50, "bullish_ratio": 0.16, "avg_base_score": 52.0, "market_score": 5},
            data_date="2026-06-13",
        )
        # Should be 2 messages: msg1 (strong) + msg3 (summary)
        assert len(msgs) == 2

    def test_with_weak_stocks_produces_msg2(self):
        """When weak stocks present, produce a weakness alert message."""
        msgs = build_broadcast_messages(
            strong_stocks=[make_result()],
            weak_stocks=[make_weak_result()],
            market_stats={"bullish_count": 5, "universe_size": 50, "bullish_ratio": 0.1, "avg_base_score": 48.0, "market_score": 4},
            data_date="2026-06-13",
        )
        assert len(msgs) == 3
        # Message 2 should contain weakness alert
        assert "轉弱" in msgs[1] or "警示" in msgs[1]

    def test_disclaimer_in_last_message(self):
        """Disclaimer appears in the last message."""
        msgs = build_broadcast_messages(
            strong_stocks=[make_result()],
            weak_stocks=[],
            market_stats=None,
            data_date="2026-06-13",
        )
        assert "不構成投資建議" in msgs[-1]

    def test_none_market_stats_handled(self):
        """None market_stats is gracefully handled."""
        msgs = build_broadcast_messages(
            strong_stocks=[make_result()],
            weak_stocks=[],
            market_stats=None,
            data_date="2026-06-13",
        )
        assert len(msgs) >= 1
        for msg in msgs:
            assert "None" not in msg
            assert "nan" not in msg.lower()

    def test_market_stats_with_none_values(self):
        """market_stats dict with None values → no None/nan in output."""
        msgs = build_broadcast_messages(
            strong_stocks=[make_result()],
            weak_stocks=[],
            market_stats={"bullish_count": None, "universe_size": None, "bullish_ratio": None, "avg_base_score": None, "market_score": None},
            data_date="2026-06-13",
        )
        for msg in msgs:
            assert "None" not in msg
            assert "nan" not in msg.lower()


# ══════════════════════════════════════════════════════════════════════════════
# 5. format_single_stock_query
# ══════════════════════════════════════════════════════════════════════════════

class TestFormatSingleStockQuery:
    def test_returns_string(self):
        result = make_result()
        text = format_single_stock_query(result)
        assert isinstance(text, str)

    def test_within_limit(self):
        result = make_result(
            positive_reasons=["a" * 100] * 5,
            negative_reasons=["b" * 100] * 4,
            risk_notes=["c" * 100] * 4,
        )
        text = format_single_stock_query(result)
        assert len(text) <= LINE_MESSAGE_MAX_CHARS

    def test_no_none_nan(self):
        result = make_result()
        text = format_single_stock_query(result)
        assert "None" not in text
        assert "nan" not in text.lower()

    def test_no_none_with_all_optional_none(self):
        """All Optional fields = None → no None/nan."""
        result = StockRadarResult(
            ticker="Y.TW", code="Y", name="Y Co",
            data_date="2026-06-13",
            latest_close=100.0, price_change_1d_pct=0.0, price_change_5d_pct=0.0,
            radar_score=45, rank_in_universe=25, universe_size=50,
            direction="neutral", confidence="低",
            trend_score=10, momentum_score=8, volume_score=10, risk_score=8, market_score=5,
            chip_score=None,
            ma5=100.0, ma20=99.0, ma60=None,
            rsi14=50.0, macd_hist=0.0, macd_hist_delta=0.0,
            volume_ratio=1.0, atr14=2.0, atr_pct=2.0,
            support_20d=95.0, resistance_20d=105.0,
            positive_reasons=[], negative_reasons=[], risk_notes=[], invalidation_conditions=[],
        )
        text = format_single_stock_query(result)
        assert "None" not in text
        assert "nan" not in text.lower()

    def test_contains_disclaimer(self):
        result = make_result()
        text = format_single_stock_query(result)
        assert "不構成投資建議" in text

    def test_contains_stock_code(self):
        result = make_result(code="2330")
        text = format_single_stock_query(result)
        assert "2330" in text

    def test_contains_score(self):
        result = make_result(radar_score=78)
        text = format_single_stock_query(result)
        assert "78" in text


# ══════════════════════════════════════════════════════════════════════════════
# 6. Edge cases — NaN/Inf inputs to make_result
# ══════════════════════════════════════════════════════════════════════════════

class TestNanInfInputs:
    """Formatter must handle NaN/Inf float inputs gracefully."""

    def test_nan_close_price(self):
        result = make_result(latest_close=float("nan"))
        text = format_stock_block(result, rank=1)
        assert "nan" not in text.lower()
        assert "None" not in text

    def test_inf_pct_change(self):
        result = make_result(price_change_1d_pct=float("inf"))
        text = format_stock_block(result, rank=1)
        assert "inf" not in text.lower()
        assert "None" not in text

    def test_nan_rsi(self):
        result = make_result(rsi14=float("nan"))
        text = format_stock_block(result, rank=1)
        assert "nan" not in text.lower()

    def test_nan_volume_ratio(self):
        result = make_result(volume_ratio=float("nan"))
        text = format_stock_block(result, rank=1)
        assert "nan" not in text.lower()
