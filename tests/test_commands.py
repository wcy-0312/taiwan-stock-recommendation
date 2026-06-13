"""
tests/test_commands.py — Unit tests for the LINE Bot command dispatcher (V3).

Tests:
    - _normalise_code: "2330" -> "2330.TW", "2330.tw" -> "2330.TW", etc.
    - dispatch_command returns list[dict] (not list[str])
    - Greeting intent: "你好", "嗨", "hi", "hello" -> dict with type "text" and quickReply
    - Unknown command: friendly message with quickReply, no "指令xxx無法識別"
    - Query not found: guidance message with 強勢股/熱門股票/可查股票 options
    - 強勢股, 轉弱股, 熱門股票, 可查股票 commands are recognized
    - Bare 4-digit code "2330" triggers query (same as "查 2330")
    - 查 <CODE> with and without cache
    - 追蹤 / 移除 / 我的清單 watchlist operations
    - 今日雷達 with and without cache
    - User isolation: different users have independent watchlists
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


# ==============================================================================
# Fixtures
# ==============================================================================

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


# ==============================================================================
# 1. _normalise_code
# ==============================================================================

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


# ==============================================================================
# 2. dispatch_command return type — list[dict]
# ==============================================================================

class TestDispatchReturnType:
    """dispatch_command must always return a list of dicts (LINE message objects)."""

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
        "你好",
        "嗨",
        "hi",
        "hello",
        "強勢股",
        "轉弱股",
        "熱門股票",
        "可查股票",
        "2330",
    ])
    def test_returns_list_of_dicts(self, text):
        from app.linebot.commands import dispatch_command

        with patch("app.linebot.commands._get_cached_radar", return_value=None):
            with patch("app.linebot.commands._get_today_cached_summary", return_value=None):
                result = dispatch_command("test_user_id", text)

        assert isinstance(result, list), f"Expected list, got {type(result)}"
        assert len(result) >= 1, "Must return at least one message"
        for msg in result:
            assert isinstance(msg, dict), f"Each item must be dict, got {type(msg)}"
            assert "type" in msg, "Each message dict must have a 'type' key"

    def test_does_not_return_list_of_strings(self):
        """Regression: old version returned list[str]; new version returns list[dict]."""
        from app.linebot.commands import dispatch_command

        with patch("app.linebot.commands._get_cached_radar", return_value=None):
            result = dispatch_command("test_user", "查 2330")

        assert isinstance(result[0], dict), "V3 must return dicts, not strings"


# ==============================================================================
# 3. Greeting intent
# ==============================================================================

class TestGreetingCommand:
    """Greeting words must NOT fall through to unknown-command."""

    @pytest.mark.parametrize("text", ["你好", "嗨", "hi", "hello", "Hello", "HI", "HELLO", "哈囉"])
    def test_greeting_returns_text_dict(self, text):
        from app.linebot.commands import dispatch_command

        result = dispatch_command("user_greet", text)

        assert isinstance(result, list)
        assert len(result) == 1
        msg = result[0]
        assert msg["type"] == "text", f"Greeting must return text type, got {msg['type']}"

    @pytest.mark.parametrize("text", ["你好", "嗨", "hi", "hello"])
    def test_greeting_has_quick_reply(self, text):
        from app.linebot.commands import dispatch_command

        result = dispatch_command("user_greet2", text)
        msg = result[0]
        assert "quickReply" in msg, "Greeting message must include quickReply"
        assert "items" in msg["quickReply"], "quickReply must have items"

    @pytest.mark.parametrize("text", ["你好", "嗨", "hi", "hello"])
    def test_greeting_not_unknown_command(self, text):
        """Greeting must not be treated as unknown command."""
        from app.linebot.commands import dispatch_command

        result = dispatch_command("user_greet3", text)
        msg_text = result[0].get("text", "")
        # Unknown command message contains "看不懂"; greeting should NOT
        assert "看不懂" not in msg_text, f"Greeting '{text}' was misrouted to unknown-command handler"


# ==============================================================================
# 4. Unknown command — friendly fallback with quickReply
# ==============================================================================

class TestFallbackCommand:
    @pytest.mark.parametrize("text", [
        "隨機文字",
        "buy 2330",
        "!@#$%",
        "完全不認識的指令",
    ])
    def test_unknown_returns_dict_with_quick_reply(self, text):
        from app.linebot.commands import dispatch_command

        with patch("app.linebot.commands._get_cached_radar", return_value=None):
            result = dispatch_command("user_unknown", text)

        assert isinstance(result, list)
        assert len(result) >= 1
        msg = result[0]
        assert isinstance(msg, dict)
        assert "quickReply" in msg, "Unknown command response must include quickReply"

    @pytest.mark.parametrize("text", [
        "隨機文字",
        "buy 2330",
    ])
    def test_unknown_does_not_contain_old_error_pattern(self, text):
        """Must NOT say '指令xxx無法識別' (old V1/V2 pattern)."""
        from app.linebot.commands import dispatch_command

        with patch("app.linebot.commands._get_cached_radar", return_value=None):
            result = dispatch_command("user_unknown2", text)

        msg_text = result[0].get("text", "")
        assert "無法識別" not in msg_text, "V3 must not use '無法識別' phrasing"
        assert "指令" not in msg_text or "指令" not in msg_text[:10], \
            "V3 should not start with '指令xxx' error format"

    def test_unknown_message_not_empty(self):
        from app.linebot.commands import dispatch_command

        result = dispatch_command("user_unknown3", "xyz_garbage_123")
        assert len(result[0].get("text", "")) > 0


# ==============================================================================
# 5. Query not found — guidance in response
# ==============================================================================

class TestQueryNotFound:
    def test_not_found_returns_guidance(self):
        """Stock not found must include guidance (0050/強勢股/熱門股票/可查股票)."""
        from app.linebot.commands import dispatch_command

        with patch("app.linebot.commands._get_cached_radar", return_value=None):
            result = dispatch_command("user_nf", "查 9999")

        assert isinstance(result, list)
        msg = result[0]
        assert isinstance(msg, dict)
        msg_text = msg.get("text", "")
        # Must contain at least one piece of guidance
        guidance_terms = ["0050", "強勢股", "熱門股票", "可查股票", "今日"]
        assert any(term in msg_text for term in guidance_terms), (
            f"not-found message must contain guidance, got: {msg_text!r}"
        )

    def test_not_found_has_quick_reply(self):
        from app.linebot.commands import dispatch_command

        with patch("app.linebot.commands._get_cached_radar", return_value=None):
            result = dispatch_command("user_nf2", "查 8888")

        msg = result[0]
        assert "quickReply" in msg, "not-found message must have quickReply"

    def test_not_found_mentions_code(self):
        """not-found message must mention the queried code."""
        from app.linebot.commands import dispatch_command

        with patch("app.linebot.commands._get_cached_radar", return_value=None):
            result = dispatch_command("user_nf3", "查 1234")

        msg_text = result[0].get("text", "")
        assert "1234" in msg_text

    def test_bare_code_not_found_guidance(self):
        """Bare 4-digit code not found also gives guidance."""
        from app.linebot.commands import dispatch_command

        with patch("app.linebot.commands._get_cached_radar", return_value=None):
            result = dispatch_command("user_nf4", "9999")

        msg = result[0]
        assert isinstance(msg, dict)
        msg_text = msg.get("text", "")
        guidance_terms = ["0050", "強勢股", "熱門股票", "可查股票", "今日"]
        assert any(term in msg_text for term in guidance_terms)


# ==============================================================================
# 6. New V3 commands: 強勢股, 轉弱股, 熱門股票, 可查股票
# ==============================================================================

class TestNewV3Commands:
    def test_qiang_shi_gu_recognized(self):
        """強勢股 must be a recognized command (not fallback)."""
        from app.linebot.commands import dispatch_command

        with patch("app.linebot.commands._get_strong_stocks", return_value=[]):
            result = dispatch_command("user_v3", "強勢股")

        assert isinstance(result, list)
        msg = result[0]
        assert isinstance(msg, dict)
        # If no data, returns not-ready message — must NOT be the unknown_command_message
        msg_text = msg.get("text", "")
        assert "看不懂" not in msg_text, "強勢股 should be recognized, not hit unknown-command"

    def test_zhuan_ruo_gu_recognized(self):
        """轉弱股 must be a recognized command."""
        from app.linebot.commands import dispatch_command

        with patch("app.linebot.commands._get_weak_stocks", return_value=[]):
            result = dispatch_command("user_v3b", "轉弱股")

        assert isinstance(result, list)
        msg = result[0]
        assert "看不懂" not in msg.get("text", ""), "轉弱股 should be recognized"

    def test_hot_stocks_recognized(self):
        """熱門股票 must be a recognized command returning text with quickReply."""
        from app.linebot.commands import dispatch_command

        result = dispatch_command("user_v3c", "熱門股票")

        assert isinstance(result, list)
        msg = result[0]
        assert msg["type"] == "text"
        assert "quickReply" in msg

    def test_ke_cha_gu_piao_recognized(self):
        """可查股票 must be a recognized command."""
        from app.linebot.commands import dispatch_command

        with patch("app.linebot.commands._load_universe_tickers", return_value=["2330", "2317"]):
            result = dispatch_command("user_v3d", "可查股票")

        assert isinstance(result, list)
        msg = result[0]
        assert "看不懂" not in msg.get("text", ""), "可查股票 should be recognized"

    def test_hot_stocks_quick_reply_has_stocks(self):
        """熱門股票 quickReply items must include actual stock codes."""
        from app.linebot.commands import dispatch_command

        result = dispatch_command("user_v3e", "熱門股票")
        msg = result[0]
        items = msg["quickReply"]["items"]
        # At least one item action should send a query command
        actions = [item["action"]["text"] for item in items]
        assert any("查" in a for a in actions), "熱門股票 quickReply must include 查 actions"


# ==============================================================================
# 7. Bare 4-digit code triggers query
# ==============================================================================

class TestBareCodeQuery:
    def test_bare_2330_triggers_query(self):
        """Bare '2330' must behave identically to '查 2330'."""
        from app.linebot.commands import dispatch_command

        with patch("app.linebot.commands._get_cached_radar", return_value=None) as mock_cache:
            result_bare = dispatch_command("user_bare", "2330")

        with patch("app.linebot.commands._get_cached_radar", return_value=None):
            result_query = dispatch_command("user_bare2", "查 2330")

        # Both should produce not-found guidance (same semantic behavior)
        assert isinstance(result_bare, list)
        assert isinstance(result_query, list)
        bare_text = result_bare[0].get("text", "")
        query_text = result_query[0].get("text", "")
        # Both mention "2330" and guidance
        assert "2330" in bare_text
        assert "2330" in query_text

    @pytest.mark.parametrize("code", ["2330", "2317", "2454", "0050"])
    def test_various_bare_codes_recognized(self, code):
        """Bare 4-digit codes should not hit the unknown-command handler."""
        from app.linebot.commands import dispatch_command

        with patch("app.linebot.commands._get_cached_radar", return_value=None):
            result = dispatch_command("user_bare3", code)

        msg_text = result[0].get("text", "")
        assert "看不懂" not in msg_text, f"Bare code {code} fell through to unknown-command"

    def test_bare_code_not_5digit(self):
        """5-digit string should NOT be treated as a stock code."""
        from app.linebot.commands import dispatch_command

        with patch("app.linebot.commands._get_cached_radar", return_value=None):
            result = dispatch_command("user_bare4", "23300")

        # 5-digit falls to unknown command handler
        msg = result[0]
        assert isinstance(msg, dict)
        # We just verify it doesn't crash; content may vary


# ==============================================================================
# 8. Help command
# ==============================================================================

class TestHelpCommand:
    @pytest.mark.parametrize("text", ["幫助", "help", "Help", "HELP", "功能", "怎麼用"])
    def test_help_variants_return_dict(self, text):
        from app.linebot.commands import dispatch_command

        result = dispatch_command("user_help", text)
        assert isinstance(result, list)
        assert len(result) == 1
        msg = result[0]
        assert isinstance(msg, dict)
        assert msg["type"] == "text"

    def test_help_has_quick_reply(self):
        from app.linebot.commands import dispatch_command

        result = dispatch_command("user_help2", "幫助")
        msg = result[0]
        assert "quickReply" in msg

    def test_help_text_contains_key_commands(self):
        from app.linebot.commands import dispatch_command

        result = dispatch_command("user_help3", "幫助")
        msg_text = result[0]["text"]
        assert "查" in msg_text
        assert "追蹤" in msg_text
        assert "移除" in msg_text
        assert "不構成投資建議" in msg_text


# ==============================================================================
# 9. 查 <CODE> command
# ==============================================================================

class TestQueryCommand:
    def test_query_2330_no_cache(self):
        """查 2330 with no cache returns not-found dict."""
        from app.linebot.commands import dispatch_command

        with patch("app.linebot.commands._get_cached_radar", return_value=None):
            result = dispatch_command("user1", "查 2330")

        assert isinstance(result, list)
        assert len(result) == 1
        msg = result[0]
        assert isinstance(msg, dict)
        assert "2330" in msg.get("text", "")

    def test_query_with_cache_hit_returns_flex(self):
        """查 2330 with cached result returns a flex or text dict."""
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
        msg = result[0]
        assert isinstance(msg, dict)
        assert msg["type"] in ("flex", "text")

        # Serialized message must not contain Python None or nan strings
        import json
        serialized = json.dumps(msg)
        assert "None" not in serialized
        assert "nan" not in serialized.lower()

    def test_query_with_cache_has_quick_reply(self):
        """Successful query result must include quickReply."""
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
            result = dispatch_command("user_qr", "查 2330")

        msg = result[0]
        assert "quickReply" in msg, "Query result with cache hit must have quickReply"

    @pytest.mark.parametrize("text", [
        "查 2330",
        "查 2317",
        "查 2454",
        "查 2330.TW",
    ])
    def test_query_various_codes(self, text):
        """查 <CODE> in various forms returns list without error."""
        from app.linebot.commands import dispatch_command

        with patch("app.linebot.commands._get_cached_radar", return_value=None):
            result = dispatch_command("user1", text)

        assert isinstance(result, list)
        assert len(result) >= 1
        assert isinstance(result[0], dict)


# ==============================================================================
# 10. 追蹤 <CODE> — add to watchlist
# ==============================================================================

class TestAddWatchlistCommand:
    def test_add_2330(self):
        from app.linebot.commands import dispatch_command

        result = dispatch_command("user1", "追蹤 2330")
        assert isinstance(result, list)
        assert len(result) == 1
        msg = result[0]
        assert isinstance(msg, dict)
        assert "2330" in msg.get("text", "")

    def test_add_returns_confirmation_dict(self):
        from app.linebot.commands import dispatch_command

        result = dispatch_command("user_add", "追蹤 2454")
        msg = result[0]
        assert msg["type"] == "text"
        assert "2454" in msg["text"]

    def test_add_already_present_is_idempotent(self):
        """Adding same ticker twice — second returns 'already in list', no crash."""
        from app.linebot.commands import dispatch_command

        dispatch_command("user1", "追蹤 2330")
        result = dispatch_command("user1", "追蹤 2330")
        assert isinstance(result, list)
        assert len(result) == 1
        assert isinstance(result[0], dict)

    def test_add_returns_confirmation_or_duplicate(self):
        """First add returns confirmation; second returns duplicate notice."""
        from app.linebot.commands import dispatch_command

        r1 = dispatch_command("user2", "追蹤 2454")
        r2 = dispatch_command("user2", "追蹤 2454")
        assert isinstance(r1, list) and isinstance(r2, list)
        # r1 should be an "added" message
        assert "2454" in r1[0].get("text", "")
        # r2 should be "already in list"
        r2_text = r2[0].get("text", "")
        assert "已在" in r2_text or "already" in r2_text.lower() or "ℹ" in r2_text

    def test_add_has_quick_reply(self):
        from app.linebot.commands import dispatch_command

        result = dispatch_command("user_add_qr", "追蹤 2330")
        assert "quickReply" in result[0]


# ==============================================================================
# 11. 移除 <CODE> — remove from watchlist
# ==============================================================================

class TestRemoveWatchlistCommand:
    def test_remove_not_present(self):
        """Removing ticker not in list returns 'not in list' message."""
        from app.linebot.commands import dispatch_command

        result = dispatch_command("user3", "移除 2330")
        assert isinstance(result, list)
        assert len(result) == 1
        assert isinstance(result[0], dict)
        msg_text = result[0].get("text", "")
        assert "不在" in msg_text or "ℹ" in msg_text

    def test_add_then_remove(self):
        """Add then remove — final watchlist is empty."""
        from app.linebot.commands import dispatch_command
        from app.linebot.watchlist import get_watchlist

        dispatch_command("user4", "追蹤 2330")
        result = dispatch_command("user4", "移除 2330")
        assert isinstance(result, list)
        assert "2330" in result[0].get("text", "")

        remaining = get_watchlist("user4")
        assert "2330.TW" not in remaining

    def test_remove_idempotent(self):
        """Removing ticker twice — second remove returns 'not in list', no crash."""
        from app.linebot.commands import dispatch_command

        dispatch_command("user5", "追蹤 2317")
        dispatch_command("user5", "移除 2317")
        result = dispatch_command("user5", "移除 2317")
        assert isinstance(result, list)
        assert isinstance(result[0], dict)

    def test_remove_has_quick_reply(self):
        from app.linebot.commands import dispatch_command

        dispatch_command("user_rm_qr", "追蹤 2330")
        result = dispatch_command("user_rm_qr", "移除 2330")
        assert "quickReply" in result[0]


# ==============================================================================
# 12. 我的清單 — watchlist listing
# ==============================================================================

class TestWatchlistListCommand:
    def test_empty_watchlist_message(self):
        """Empty watchlist returns appropriate message dict."""
        from app.linebot.commands import dispatch_command

        result = dispatch_command("user6", "我的清單")
        assert isinstance(result, list)
        assert len(result) == 1
        msg = result[0]
        assert isinstance(msg, dict)
        msg_text = msg.get("text", "")
        assert "空" in msg_text or "empty" in msg_text.lower() or "沒有" in msg_text

    def test_watchlist_shows_added_tickers(self):
        """After adding tickers, 我的清單 shows them."""
        from app.linebot.commands import dispatch_command

        dispatch_command("user7", "追蹤 2330")
        dispatch_command("user7", "追蹤 2317")

        with patch("app.linebot.commands._get_cached_radar", return_value=None):
            result = dispatch_command("user7", "我的清單")

        assert isinstance(result, list)
        assert len(result) == 1
        msg = result[0]
        assert isinstance(msg, dict)
        # Text fallback or altText should mention the tickers
        content = msg.get("text", "") + msg.get("altText", "")
        assert "2330.TW" in content or "2330" in content
        assert "2317.TW" in content or "2317" in content

    def test_watchlist_after_remove(self):
        """Watchlist reflects removal correctly."""
        from app.linebot.commands import dispatch_command

        dispatch_command("user8", "追蹤 2330")
        dispatch_command("user8", "追蹤 2317")
        dispatch_command("user8", "移除 2330")

        with patch("app.linebot.commands._get_cached_radar", return_value=None):
            result = dispatch_command("user8", "我的清單")

        msg = result[0]
        content = msg.get("text", "") + msg.get("altText", "")
        assert "2317" in content
        assert "2330" not in content or content.count("2330") == 0

    def test_empty_watchlist_has_quick_reply(self):
        from app.linebot.commands import dispatch_command

        result = dispatch_command("user_wl_qr", "我的清單")
        assert "quickReply" in result[0]


# ==============================================================================
# 13. 今日雷達 command
# ==============================================================================

class TestTodayRadarCommand:
    def test_no_cache_returns_not_ready(self):
        """今日雷達 with no cache returns not-ready message dict."""
        from app.linebot.commands import dispatch_command

        with patch("app.linebot.commands._get_today_cached_summary", return_value=None):
            result = dispatch_command("user9", "今日雷達")

        assert isinstance(result, list)
        assert len(result) == 1
        msg = result[0]
        assert isinstance(msg, dict)
        msg_text = msg.get("text", "")
        assert "尚未" in msg_text or "就緒" in msg_text or "not ready" in msg_text.lower()

    def test_no_cache_has_quick_reply(self):
        from app.linebot.commands import dispatch_command

        with patch("app.linebot.commands._get_today_cached_summary", return_value=None):
            result = dispatch_command("user9b", "今日雷達")

        assert "quickReply" in result[0]

    def test_with_cache_returns_summary(self):
        """今日雷達 with cached summary returns summary in a text message dict."""
        from app.linebot.commands import dispatch_command

        mock_summary = "📊 台股技術雷達 2026-06-13\n─────\n市場環境：10/50 偏多"
        with patch("app.linebot.commands._get_today_cached_summary", return_value=mock_summary):
            result = dispatch_command("user9", "今日雷達")

        assert isinstance(result, list)
        msg = result[0]
        assert isinstance(msg, dict)
        assert msg.get("text") == mock_summary


# ==============================================================================
# 14. User isolation — different users have independent watchlists
# ==============================================================================

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
