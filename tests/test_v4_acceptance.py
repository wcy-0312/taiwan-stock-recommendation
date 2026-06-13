"""
tests/test_v4_acceptance.py — V4 Product Acceptance Tests (10 scenarios).

1.  test_product_name_unified        — FastAPI title = "台股智能雷達"
2.  test_public_base_url_in_health   — /health includes public_base_url_configured
3.  test_latest_cache_loads          — load_latest_analysis_cache() works without today
4.  test_cache_date_label            — get_latest_analysis_date() returns correct format
5.  test_news_command_no_data        — "新聞" command with no data returns friendly text
6.  test_news_command_with_data      — "新聞" command with data returns Flex Message
7.  test_unknown_command_message     — unknown command returns new V4 text
8.  test_watchlist_flex_full_data    — watchlist flex contains name/score/direction
9.  test_stock_history_api_no_data   — /api/stock/9999/history returns 200 + error key
10. test_hot_stocks_includes_2412    — 2412 中華電 in HOT_STOCKS
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from typing import Optional
from unittest.mock import patch, MagicMock

import pytest

# Ensure project root is on sys.path
_PROJECT_ROOT = str(Path(__file__).parent.parent)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)


# ---------------------------------------------------------------------------
# Test 1: FastAPI title
# ---------------------------------------------------------------------------

def test_product_name_unified():
    """FastAPI app title must be '台股智能雷達'."""
    try:
        from app.main import app
        assert app.title == "台股智能雷達", f"Expected '台股智能雷達', got '{app.title}'"
    except ImportError:
        pytest.skip("app.main not importable")


# ---------------------------------------------------------------------------
# Test 2: /health includes public_base_url_configured
# ---------------------------------------------------------------------------

def test_public_base_url_in_health(monkeypatch):
    """GET /health must include public_base_url_configured field."""
    try:
        monkeypatch.setenv("LINE_CHANNEL_ACCESS_TOKEN", "test_token")
        monkeypatch.setenv("LINE_USER_ID", "test_user")
        monkeypatch.setenv("LINE_CHANNEL_SECRET", "test_secret")
        monkeypatch.setenv("PUBLIC_BASE_URL", "https://test.example.com")

        from fastapi.testclient import TestClient
        from app.main import app
        client = TestClient(app)
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert "public_base_url_configured" in data, (
            "/health response must include 'public_base_url_configured'"
        )
    except ImportError:
        pytest.skip("app not importable")


# ---------------------------------------------------------------------------
# Test 3: load_latest_analysis_cache() not limited to today
# ---------------------------------------------------------------------------

def test_latest_cache_loads():
    """load_latest_analysis_cache() must return data even when cache is from a past date."""
    with tempfile.TemporaryDirectory() as tmpdir:
        cache_dir = Path(tmpdir)
        # Create a cache file with a past date
        cache_file = cache_dir / "analysis_2026-06-06.json"
        payload = {
            "results": [{"ticker": "2330.TW", "code": "2330", "radar_score": 75}],
            "market_stats": {"market_score": 6},
        }
        cache_file.write_text(json.dumps(payload), encoding="utf-8")

        # Patch CACHE_DIR
        with patch("app.cache.latest_cache.CACHE_DIR", cache_dir):
            from app.cache.latest_cache import load_latest_analysis_cache
            import importlib
            import app.cache.latest_cache as m
            importlib.reload(m)
            # Directly call with patched CACHE_DIR
            with patch.object(m, "CACHE_DIR", cache_dir):
                result = m.load_latest_analysis_cache()

        assert result is not None, "load_latest_analysis_cache() must not return None for past dates"
        assert "results" in result


# ---------------------------------------------------------------------------
# Test 4: get_latest_analysis_date() format
# ---------------------------------------------------------------------------

def test_cache_date_label():
    """get_latest_analysis_date() must return 'YYYY-MM-DD' format or '—'."""
    import re
    with tempfile.TemporaryDirectory() as tmpdir:
        cache_dir = Path(tmpdir)

        import app.cache.latest_cache as m
        import importlib
        importlib.reload(m)

        with patch.object(m, "CACHE_DIR", cache_dir):
            # No files — returns "—"
            date_str = m.get_latest_analysis_date()
            assert date_str == "—", f"Expected '—', got '{date_str}'"

            # Create a dated cache file
            (cache_dir / "analysis_2026-06-10.json").write_text(
                '{"results":[], "market_stats":{}}', encoding="utf-8"
            )
            date_str = m.get_latest_analysis_date()
            assert re.match(r"^\d{4}-\d{2}-\d{2}$", date_str), (
                f"Expected YYYY-MM-DD format, got '{date_str}'"
            )
            assert date_str == "2026-06-10"


# ---------------------------------------------------------------------------
# Test 5: "新聞" command with no data returns friendly text
# ---------------------------------------------------------------------------

def test_news_command_no_data():
    """'新聞' command when no market events file exists returns a friendly text response."""
    try:
        from app.linebot.commands import dispatch_command
    except ImportError:
        pytest.skip("commands not importable")

    # Patch _load_market_events to return empty list
    with patch("app.linebot.commands._load_market_events", return_value=[]):
        results = dispatch_command("user_001", "新聞")

    assert len(results) >= 1
    first = results[0]
    assert first["type"] == "text"
    assert "目前無市場事件" in first["text"] or "稍後" in first["text"]


# ---------------------------------------------------------------------------
# Test 6: "新聞" command with data returns Flex Message
# ---------------------------------------------------------------------------

def test_news_command_with_data():
    """'新聞' command when events are present returns a Flex Message."""
    try:
        from app.linebot.commands import dispatch_command
    except ImportError:
        pytest.skip("commands not importable")

    sample_events = [
        {
            "id": "e001",
            "date": "2026-06-13",
            "title": "Fed 維持利率不變",
            "category": "總體經濟",
            "summary": "FOMC 決議...",
            "impact": "neutral",
        }
    ]

    with patch("app.linebot.commands._load_market_events", return_value=sample_events):
        results = dispatch_command("user_001", "新聞")

    assert len(results) >= 1
    first = results[0]
    assert first["type"] == "flex", f"Expected 'flex', got '{first['type']}'"
    assert "altText" in first
    assert "市場" in first["altText"] or "事件" in first["altText"]


# ---------------------------------------------------------------------------
# Test 7: Unknown command returns new V4 text
# ---------------------------------------------------------------------------

def test_unknown_command_message():
    """Unknown command must return new V4 text mentioning '新聞'."""
    try:
        from app.linebot.flex_templates import unknown_command_message
    except ImportError:
        pytest.skip("flex_templates not importable")

    msg = unknown_command_message("tell me the best stock to buy")
    assert msg["type"] == "text"
    # V4 text must NOT contain the old "找不到…雷達資料" pattern
    assert "找不到" not in msg["text"] or "雷達資料" not in msg["text"]
    # V4 text must contain guidance keywords
    assert "新聞" in msg["text"], "V4 unknown command text should mention '新聞'"
    assert "強勢股" in msg["text"] or "雷達" in msg["text"]


# ---------------------------------------------------------------------------
# Test 8: 我的清單 flex contains name/score/direction
# ---------------------------------------------------------------------------

def test_watchlist_flex_full_data():
    """watchlist_flex with full radar data must show name, score, direction."""
    try:
        from app.linebot.flex_templates import watchlist_flex
        from app.scoring.models import StockRadarResult
    except ImportError:
        pytest.skip("dependencies not importable")

    # Build a minimal StockRadarResult
    r = StockRadarResult(
        ticker="2330.TW",
        code="2330",
        name="台積電",
        data_date="2026-06-13",
        latest_close=1000.0,
        price_change_1d_pct=1.5,
        price_change_5d_pct=3.0,
        radar_score=82,
        rank_in_universe=1,
        universe_size=50,
        direction="bullish",
        confidence="高",
        trend_score=25,
        momentum_score=18,
        volume_score=16,
        risk_score=12,
        market_score=8,
        chip_score=None,
        ma5=998.0,
        ma20=980.0,
        ma60=950.0,
        rsi14=62.0,
        macd_hist=2.5,
        macd_hist_delta=0.5,
        volume_ratio=1.4,
        atr14=15.0,
        atr_pct=1.5,
        support_20d=960.0,
        resistance_20d=1020.0,
        positive_reasons=["MA5 > MA20 多頭排列"],
        negative_reasons=[],
        risk_notes=[],
        invalidation_conditions=[],
    )
    msg = watchlist_flex(["2330.TW"], {"2330.TW": r})
    serialized = json.dumps(msg, ensure_ascii=False)

    assert msg["type"] == "flex"
    # Should contain stock name
    assert "台積電" in serialized, "Watchlist flex must show stock name"
    # Should contain radar score
    assert "82" in serialized, "Watchlist flex must show radar score"
    # Should contain direction indicator
    assert "🟢" in serialized or "bullish" in serialized.lower() or "偏多" in serialized, (
        "Watchlist flex must indicate direction"
    )


# ---------------------------------------------------------------------------
# Test 9: /api/stock/9999/history returns HTTP 200 + error key
# ---------------------------------------------------------------------------

def test_stock_history_api_no_data(monkeypatch):
    """GET /api/stock/9999/history must return HTTP 200 with 'error' key on failure."""
    try:
        monkeypatch.setenv("LINE_CHANNEL_ACCESS_TOKEN", "test_token")
        monkeypatch.setenv("LINE_USER_ID", "test_user")
        monkeypatch.setenv("LINE_CHANNEL_SECRET", "test_secret")

        # Mock yfinance to return empty DataFrame
        import pandas as pd

        mock_yf = MagicMock()
        mock_yf.download.return_value = pd.DataFrame()

        with patch.dict("sys.modules", {"yfinance": mock_yf}):
            from fastapi.testclient import TestClient
            from app.main import app
            client = TestClient(app)
            resp = client.get("/api/stock/9999/history")

        assert resp.status_code == 200, (
            f"Expected HTTP 200, got {resp.status_code} (DL-3: yfinance failure → 200 + error)"
        )
        data = resp.json()
        assert "error" in data, "Response must contain 'error' key when yfinance fails"
    except ImportError:
        pytest.skip("app not importable")


# ---------------------------------------------------------------------------
# Test 10: HOT_STOCKS includes 2412 中華電
# ---------------------------------------------------------------------------

def test_hot_stocks_includes_2412():
    """HOT_STOCKS must include 2412 中華電 (V4 update)."""
    try:
        from app.linebot.flex_templates import HOT_STOCKS
    except ImportError:
        pytest.skip("flex_templates not importable")

    # HOT_STOCKS is a list of dicts: {"code": ..., "name": ...}
    codes = [s["code"] if isinstance(s, dict) else s[0] for s in HOT_STOCKS]
    assert "2412" in codes, (
        f"HOT_STOCKS must include 2412 中華電. Found codes: {codes}"
    )
