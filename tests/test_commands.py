"""
tests/test_commands.py — Unit tests for the LINE Bot command dispatcher.

Tests:
    - _normalise_code: "2330" → "2330.TW", "2330.tw" → "2330.TW", etc.
    - dispatch_command: "2330" bare code (plain number) → returns list of strings
    - dispatch_command: "查 2330" → stock query reply
    - dispatch_command: "追蹤 2330" → watchlist add reply
    - dispatch_command: "取消追蹤 2330" (via "移除 2330") → watchlist remove reply
    - dispatch_command: "我的清單" → watchlist listing
    - dispatch_command: "幫助" / "help" → HELP_TEXT
    - dispatch_command: unknown input → fallback help
    - Watchlist add/remove/list are idempotent (no crash on duplicate)
    - Returns list of strings (not bare strings)
    - dispatch_command: "今日雷達" → radar summary or "尚未就緒" message
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

_PROJECT_ROOT = Path(__file__).parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))


# ══════════════════════════════════════════════════════════════════════════════
# Fixtures
# ══════════════════════════════════════════════════════════════════════════════

@pytest.fixture(autouse=True)
def isolated_watchlist_db(tmp_path):
    """
    Redirect WATCHLIST_DB_PATH to a temp file for each test.
    This ensures watchlist tests are isolated.
    """
    db_path = tmp_path / "test_watchlist.db"
    with patch("app.config.WATCHLIST_DB_PATH", db_path):
        with patch("app.linebot.watchlist.WATCHLIST_DB_PATH", db_path):
            yield db_path


# ══════════════════════════════════════════════════════════════════════════════
# 1. _normalise_code
# ══════════════════════════════════════════════════════════════════════════════

class TestNormaliseCode:
    def _normalise(self, raw: str) -> str:
        from app.linebot.commands import _normalise_code
        return _normalise_code(raw)

    def test_bare_4digit_code(self):
        assert self._normalise("2330") == "2330.TW"

    def test_lowercase_suffix(self):
        assert self._normalise("2330.tw") == "2330.TW"

    def test_uppercase_suffix_passthrough(self):
        assert self._normalise("2330.TW") == "2330.TW"

    def test_mixed_case_suffix(self):
        assert self._normalise("2330.Tw") == "2330.TW"

    def test_whitespace_stripped(self):
        assert self._normalise("  2330  ") == "2330.TW"

    def test_alpha_ticker(self):
        assert self._normalise("TSM") == "TSM.TW"

    def test_already_has_tw_no_double(self):
        """Should not add .TW twice."""
        result = self._normalise("2330.TW")
        assert result.count(".TW") == 1


# ══════════════════════════════════════════════════════════════════════════════
# 2. dispatch_command return type
# ══════════════════════════════════════════════════════════════════════════════

class TestDispatchReturnType:
    """dispatch_command must always return a list of strings."""

    @pytest.mark.parametrize("text", [
        "幫助", "help", "Help", "HELP",
        "我的清單",
        "今日雷達",
        "追蹤 2330",
        "移除 2330",
        "查 2330",
        "unknown_command_xyz",
        "",
        "隨機文字abc",
    ])
    def test_returns_list_of_strings(self, text):
        from app.linebot.commands import dispatch_command

        # Patch the cache lookup so no file I/O needed
        with patch("app.linebot.commands._get_cached_radar", return_value=None):
            with patch("app.linebot.commands._get_today_cached_summary", return_value=None):
                result = dispatch_command("test_user_id", text)

        assert isinstance(result, list), f"Expected list, got {type(result)}"
        assert len(result) >= 1, "Must return at least one message"
        for msg in result:
            assert isinstance(msg, str), f"Each item must be str, got {type(msg)}"
            assert len(msg) > 0, "Messages must not be empty"


# ══════════════════════════════════════════════════════════════════════════════
# 3. Help command
# ══════════════════════════════════════════════════════════════════════════════

class TestHelpCommand:
    @pytest.mark.parametrize("text", ["幫助", "help", "Help", "HELP"])
    def test_help_variants(self, text):
        from app.linebot.commands import dispatch_command, HELP_TEXT

        result = dispatch_command("user1", text)
        assert result == [HELP_TEXT]

    def test_help_contains_commands(self):
        from app.linebot.commands import HELP_TEXT
        # Verify HELP_TEXT mentions key commands
        assert "查" in HELP_TEXT
        assert "追蹤" in HELP_TEXT
        assert "移除" in HELP_TEXT or "取消" in HELP_TEXT or "移除" in HELP_TEXT
        assert "我的清單" in HELP_TEXT
        assert "幫助" in HELP_TEXT
        assert "不構成投資建議" in HELP_TEXT


# ══════════════════════════════════════════════════════════════════════════════
# 4. 查 <CODE> command
# ══════════════════════════════════════════════════════════════════════════════

class TestQueryCommand:
    def test_query_2330_no_cache(self):
        """查 2330 with no cache returns not-found message."""
        from app.linebot.commands import dispatch_command

        with patch("app.linebot.commands._get_cached_radar", return_value=None):
            result = dispatch_command("user1", "查 2330")

        assert isinstance(result, list)
        assert len(result) == 1
        assert "2330" in result[0]

    def test_query_with_cache_hit(self):
        """查 2330 with cached result returns formatted stock info."""
        from app.linebot.commands import dispatch_command
        from app.scoring.models import StockRadarResult

        mock_result = StockRadarResult(
            ticker="2330.TW", code="2330", name="台積電",
            data_date="2026-06-13",
            latest_close=900.0, price_change_1d_pct=1.5, price_change_5d_pct=3.0,
            radar_score=78, rank_in_universe=1, universe_size=50,
            direction="bullish", confidence="中",
            trend_score=22, momentum_score=15, volume_score=16, risk_score=12,
            market_score=8, chip_score=None,
            ma5=895.0, ma20=880.0, ma60=860.0,
            rsi14=62.0, macd_hist=0.3, macd_hist_delta=0.1,
            volume_ratio=1.3, atr14=14.0, atr_pct=1.6,
            support_20d=870.0, resistance_20d=920.0,
            positive_reasons=["多頭排列"], negative_reasons=[], risk_notes=[],
            invalidation_conditions=[],
        )

        with patch("app.linebot.commands._get_cached_radar", return_value=mock_result):
            result = dispatch_command("user1", "查 2330")

        assert isinstance(result, list)
        assert len(result) == 1
        assert "2330" in result[0]
        assert "None" not in result[0]
        assert "nan" not in result[0].lower()

    @pytest.mark.parametrize("text", [
        "查 2330",
        "查 2317",
        "查 2454",
        "查 2330.TW",
    ])
    def test_query_various_codes(self, text):
        """查 <CODE> in various forms → returns list without error."""
        from app.linebot.commands import dispatch_command

        with patch("app.linebot.commands._get_cached_radar", return_value=None):
            result = dispatch_command("user1", text)

        assert isinstance(result, list)
        assert len(result) >= 1


# ══════════════════════════════════════════════════════════════════════════════
# 5. 追蹤 <CODE> — add to watchlist
# ══════════════════════════════════════════════════════════════════════════════

class TestAddWatchlistCommand:
    def test_add_2330(self):
        from app.linebot.commands import dispatch_command

        result = dispatch_command("user1", "追蹤 2330")
        assert isinstance(result, list)
        assert len(result) == 1
        # Should confirm addition
        assert "2330.TW" in result[0] or "2330" in result[0]

    def test_add_already_present_is_idempotent(self):
        """Adding same ticker twice → second time gives 'already in list' message, no crash."""
        from app.linebot.commands import dispatch_command

        dispatch_command("user1", "追蹤 2330")
        result = dispatch_command("user1", "追蹤 2330")
        assert isinstance(result, list)
        assert len(result) == 1

    def test_add_returns_confirmation_or_duplicate(self):
        """First add returns confirmation; second returns duplicate notice."""
        from app.linebot.commands import dispatch_command

        r1 = dispatch_command("user2", "追蹤 2454")
        r2 = dispatch_command("user2", "追蹤 2454")
        # Both should be list of strings
        assert isinstance(r1, list) and isinstance(r2, list)
        # r1 should be an "added" message
        assert "2454.TW" in r1[0] or "2454" in r1[0]
        # r2 should be "already in list"
        assert "已在" in r2[0] or "already" in r2[0].lower() or "ℹ" in r2[0]


# ══════════════════════════════════════════════════════════════════════════════
# 6. 移除 <CODE> — remove from watchlist
# ══════════════════════════════════════════════════════════════════════════════

class TestRemoveWatchlistCommand:
    def test_remove_not_present(self):
        """Removing ticker not in list → returns 'not in list' message."""
        from app.linebot.commands import dispatch_command

        result = dispatch_command("user3", "移除 2330")
        assert isinstance(result, list)
        assert len(result) == 1
        # Should inform not in list
        assert "不在" in result[0] or "ℹ" in result[0]

    def test_add_then_remove(self):
        """Add then remove → final watchlist is empty."""
        from app.linebot.commands import dispatch_command
        from app.linebot.watchlist import get_watchlist

        dispatch_command("user4", "追蹤 2330")
        result = dispatch_command("user4", "移除 2330")
        assert isinstance(result, list)
        assert "2330.TW" in result[0] or "2330" in result[0]

        # Watchlist should be empty now
        remaining = get_watchlist("user4")
        assert "2330.TW" not in remaining

    def test_remove_idempotent(self):
        """Removing ticker twice → second remove returns 'not in list', no crash."""
        from app.linebot.commands import dispatch_command

        dispatch_command("user5", "追蹤 2317")
        dispatch_command("user5", "移除 2317")
        result = dispatch_command("user5", "移除 2317")
        assert isinstance(result, list)


# ══════════════════════════════════════════════════════════════════════════════
# 7. 我的清單 — watchlist listing
# ══════════════════════════════════════════════════════════════════════════════

class TestWatchlistListCommand:
    def test_empty_watchlist_message(self):
        """Empty watchlist → appropriate message."""
        from app.linebot.commands import dispatch_command

        result = dispatch_command("user6", "我的清單")
        assert isinstance(result, list)
        assert len(result) == 1
        assert "空" in result[0] or "empty" in result[0].lower() or "沒有" in result[0]

    def test_watchlist_shows_added_tickers(self):
        """After adding tickers, 我的清單 shows them."""
        from app.linebot.commands import dispatch_command

        dispatch_command("user7", "追蹤 2330")
        dispatch_command("user7", "追蹤 2317")

        result = dispatch_command("user7", "我的清單")
        assert isinstance(result, list)
        assert len(result) == 1
        assert "2330.TW" in result[0]
        assert "2317.TW" in result[0]

    def test_watchlist_after_remove(self):
        """Watchlist reflects removal correctly."""
        from app.linebot.commands import dispatch_command

        dispatch_command("user8", "追蹤 2330")
        dispatch_command("user8", "追蹤 2317")
        dispatch_command("user8", "移除 2330")

        result = dispatch_command("user8", "我的清單")
        assert "2317.TW" in result[0]
        assert "2330.TW" not in result[0]


# ══════════════════════════════════════════════════════════════════════════════
# 8. 今日雷達 command
# ══════════════════════════════════════════════════════════════════════════════

class TestTodayRadarCommand:
    def test_no_cache_returns_not_ready(self):
        """今日雷達 with no cache → returns not-ready message."""
        from app.linebot.commands import dispatch_command

        with patch("app.linebot.commands._get_today_cached_summary", return_value=None):
            result = dispatch_command("user9", "今日雷達")

        assert isinstance(result, list)
        assert len(result) == 1
        assert "尚未" in result[0] or "就緒" in result[0] or "not ready" in result[0].lower()

    def test_with_cache_returns_summary(self):
        """今日雷達 with cached summary → returns summary string."""
        from app.linebot.commands import dispatch_command

        mock_summary = "📊 台股技術雷達 2026-06-13\n─────\n市場環境：10/50 偏多"
        with patch("app.linebot.commands._get_today_cached_summary", return_value=mock_summary):
            result = dispatch_command("user9", "今日雷達")

        assert isinstance(result, list)
        assert result == [mock_summary]


# ══════════════════════════════════════════════════════════════════════════════
# 9. Unknown / fallback command
# ══════════════════════════════════════════════════════════════════════════════

class TestFallbackCommand:
    @pytest.mark.parametrize("text", [
        "隨機文字",
        "buy 2330",
        "!@#$%",
        "強勢股",       # not implemented in base commands.py
        "轉弱股",
    ])
    def test_unknown_returns_help_fallback(self, text):
        """Unrecognized commands return a help fallback, never crash."""
        from app.linebot.commands import dispatch_command

        with patch("app.linebot.commands._get_cached_radar", return_value=None):
            result = dispatch_command("user10", text)

        assert isinstance(result, list)
        assert len(result) >= 1
        # Should contain some guidance text
        assert len(result[0]) > 0


# ══════════════════════════════════════════════════════════════════════════════
# 10. User isolation — different users have independent watchlists
# ══════════════════════════════════════════════════════════════════════════════

class TestUserIsolation:
    def test_different_users_independent_watchlists(self):
        """Two different users have independent watchlists."""
        from app.linebot.commands import dispatch_command
        from app.linebot.watchlist import get_watchlist

        dispatch_command("alice", "追蹤 2330")
        dispatch_command("bob", "追蹤 2317")

        alice_list = get_watchlist("alice")
        bob_list = get_watchlist("bob")

        assert "2330.TW" in alice_list
        assert "2317.TW" not in alice_list
        assert "2317.TW" in bob_list
        assert "2330.TW" not in bob_list
