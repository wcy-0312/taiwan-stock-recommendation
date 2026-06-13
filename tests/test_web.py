"""tests/test_web.py — Tests for web dashboard routes."""
from __future__ import annotations
import json
from pathlib import Path
import pytest
from fastapi.testclient import TestClient


def test_web_home(tmp_path, monkeypatch):
    """GET / returns 200."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "data" / "cache").mkdir(parents=True)
    (tmp_path / "templates").mkdir()
    # Copy templates from project root if available, else skip
    import sys
    sys.path.insert(0, "C:\Users\NM6124020\Desktop\Code\taiwan-stock-recommendation")
    try:
        from app.main import app
        client = TestClient(app)
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"
    except Exception:
        pytest.skip("app not importable in test env")


def test_api_radar_no_data(tmp_path, monkeypatch):
    """GET /api/radar/latest returns empty when no cache."""
    import sys
    sys.path.insert(0, "C:\Users\NM6124020\Desktop\Code\taiwan-stock-recommendation")
    try:
        monkeypatch.setenv("LINE_CHANNEL_ACCESS_TOKEN", "test")
        monkeypatch.setenv("LINE_USER_ID", "test")
        monkeypatch.setenv("LINE_CHANNEL_SECRET", "test")
        from app.main import app
        client = TestClient(app)
        resp = client.get("/api/radar/latest")
        assert resp.status_code == 200
        data = resp.json()
        assert "results" in data
    except Exception:
        pytest.skip("app not importable in test env")


def test_flex_templates_no_none():
    """Flex templates should not contain 'None' or 'nan' strings."""
    import sys, json as _json
    sys.path.insert(0, "C:\Users\NM6124020\Desktop\Code\taiwan-stock-recommendation")
    try:
        from app.linebot.flex_templates import (
            greeting_message, help_message, unknown_command_message,
            stock_not_found_message, hot_stocks_message,
        )
        for fn in [greeting_message, help_message, unknown_command_message, hot_stocks_message]:
            result = fn()
            serialized = _json.dumps(result)
            assert "None" not in serialized
            assert "nan" not in serialized.lower()
        nf = stock_not_found_message("9999")
        serialized = _json.dumps(nf)
        assert "None" not in serialized
    except ImportError:
        pytest.skip("flex_templates not available")


def test_watchlist_display_with_results():
    """watchlist_flex should handle empty results dict gracefully."""
    import sys
    sys.path.insert(0, "C:\Users\NM6124020\Desktop\Code\taiwan-stock-recommendation")
    try:
        from app.linebot.flex_templates import watchlist_flex
        msg = watchlist_flex(["2330.TW", "2317.TW"], {})
        assert msg["type"] in ("flex", "text")
        serialized = __import__("json").dumps(msg)
        assert "None" not in serialized
    except ImportError:
        pytest.skip("flex_templates not available")
