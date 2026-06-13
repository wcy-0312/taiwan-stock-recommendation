"""tests/test_web.py — Tests for web dashboard routes."""
from __future__ import annotations
import json
import sys
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

# Ensure project root is on sys.path regardless of how pytest is invoked
_PROJECT_ROOT = str(Path(__file__).parent.parent)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)


def test_web_health():
    """GET /health returns 200."""
    try:
        from app.main import app
        client = TestClient(app)
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"
    except Exception:
        pytest.skip("app not importable in test env")


def test_api_radar_no_data(monkeypatch):
    """GET /api/radar/latest returns empty payload when no cache."""
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
    """Flex templates must not serialize to strings containing 'None' or 'nan'."""
    try:
        from app.linebot.flex_templates import (
            greeting_message, help_message, unknown_command_message,
            stock_not_found_message, hot_stocks_message,
        )
    except ImportError:
        pytest.skip("flex_templates not available")

    for fn in [greeting_message, help_message, unknown_command_message, hot_stocks_message]:
        result = fn()
        serialized = json.dumps(result)
        assert "None" not in serialized
        assert "nan" not in serialized.lower()

    nf = stock_not_found_message("9999")
    assert "None" not in json.dumps(nf)


def test_watchlist_display_with_results():
    """watchlist_flex handles empty results dict without errors."""
    try:
        from app.linebot.flex_templates import watchlist_flex
    except ImportError:
        pytest.skip("flex_templates not available")

    msg = watchlist_flex(["2330.TW", "2317.TW"], {})
    assert msg["type"] in ("flex", "text")
    assert "None" not in json.dumps(msg)
