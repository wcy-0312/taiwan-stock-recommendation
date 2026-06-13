"""
tests/test_backtest.py — Unit and integration tests for the backtesting module.

Tests:
    - compute_metrics: correct win_rate, avg_return, max_drawdown, sharpe
    - compute_metrics: insufficient sample returns None fields + sample_sufficient=False
    - compute_metrics: all-win and all-loss edge cases
    - run_backtest: small synthetic run completes without error (no live network)
    - run_backtest: returns correct structure keys
    - format_metrics_report: no None/nan in output string
    - CLI: argparse parses correctly, exits cleanly on bad input
"""

from __future__ import annotations

import math
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pandas as pd
import numpy as np
import pytest

# ── Project root on path ───────────────────────────────────────────────────────
_PROJECT_ROOT = Path(__file__).parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from app.backtesting.metrics import compute_metrics, format_metrics_report, MIN_TRADES_REQUIRED
from app.backtesting.engine import run_backtest, _compute_base_score, TradeRecord


# ══════════════════════════════════════════════════════════════════════════════
# Fixtures
# ══════════════════════════════════════════════════════════════════════════════

def make_ohlcv(n: int = 60, start_price: float = 100.0, trend: float = 0.001) -> pd.DataFrame:
    """
    Create a synthetic OHLCV DataFrame with `n` rows.

    Parameters
    ----------
    n           : number of trading days
    start_price : starting close price
    trend       : daily multiplicative drift (0.001 = +0.1%/day)
    """
    dates = pd.date_range("2024-01-02", periods=n, freq="B")
    closes = [start_price * (1 + trend) ** i for i in range(n)]
    highs = [c * 1.01 for c in closes]
    lows = [c * 0.99 for c in closes]
    opens = [c * 1.002 for c in closes]
    volumes = [1_000_000 + i * 5000 for i in range(n)]

    df = pd.DataFrame(
        {"Open": opens, "High": highs, "Low": lows, "Close": closes, "Volume": volumes},
        index=dates,
    )
    df.index.name = "Date"
    return df


def make_returns(n: int, win_rate: float = 0.6, avg_win: float = 3.0, avg_loss: float = -1.5) -> list[float]:
    """Create synthetic return list with controlled win_rate."""
    import random
    random.seed(42)
    returns = []
    for _ in range(n):
        if random.random() < win_rate:
            returns.append(avg_win + random.gauss(0, 0.5))
        else:
            returns.append(avg_loss + random.gauss(0, 0.3))
    return returns


# ══════════════════════════════════════════════════════════════════════════════
# compute_metrics tests
# ══════════════════════════════════════════════════════════════════════════════

class TestComputeMetrics:
    def test_insufficient_sample_returns_none_fields(self):
        """Fewer than MIN_TRADES_REQUIRED trades → sample_sufficient=False, all metrics None."""
        result = compute_metrics([1.0, 2.0, -1.0])  # 3 trades < 10
        assert result["sample_sufficient"] is False
        assert result["win_rate"] is None
        assert result["avg_return"] is None
        assert result["annualized_return"] is None
        assert result["max_drawdown"] is None
        assert result["sharpe_ratio"] is None
        assert result["trade_count"] == 3

    def test_empty_returns(self):
        """Empty list → sample_sufficient=False."""
        result = compute_metrics([])
        assert result["sample_sufficient"] is False
        assert result["trade_count"] == 0

    def test_sufficient_sample_win_rate(self):
        """Win rate computed correctly for known returns."""
        # 8 wins, 4 losses = 12 trades
        returns = [2.0] * 8 + [-1.0] * 4
        result = compute_metrics(returns, holding_days=5)
        assert result["sample_sufficient"] is True
        assert result["trade_count"] == 12
        assert abs(result["win_rate"] - 8 / 12) < 1e-9

    def test_avg_return(self):
        """Average return is arithmetic mean."""
        returns = [3.0, -1.0, 2.0, 0.5, -0.5] * 3  # 15 trades
        result = compute_metrics(returns, holding_days=5)
        expected_avg = sum(returns) / len(returns)
        assert abs(result["avg_return"] - expected_avg) < 1e-9

    def test_max_drawdown_all_wins(self):
        """All positive returns → max drawdown = 0."""
        returns = [1.0] * 15
        result = compute_metrics(returns, holding_days=5)
        assert result["max_drawdown"] == 0.0

    def test_max_drawdown_all_losses(self):
        """All negative returns → max drawdown > 0."""
        returns = [-1.0] * 15
        result = compute_metrics(returns, holding_days=5)
        assert result["max_drawdown"] is not None
        assert result["max_drawdown"] > 0

    def test_sharpe_ratio_positive_when_positive_returns(self):
        """Positive mean return → positive Sharpe ratio."""
        returns = [2.0] * 8 + [-0.5] * 7  # 15 trades, positive mean
        result = compute_metrics(returns, holding_days=5)
        assert result["sharpe_ratio"] is not None
        assert result["sharpe_ratio"] > 0

    def test_sharpe_ratio_none_when_zero_std(self):
        """Identical returns → std=0 → sharpe_ratio=None."""
        returns = [1.0] * 15  # all same → std=0
        result = compute_metrics(returns, holding_days=5)
        assert result["sharpe_ratio"] is None

    def test_annualized_return_finite(self):
        """Annualised return must be a finite float."""
        returns = make_returns(20, win_rate=0.6)
        result = compute_metrics(returns, holding_days=5)
        assert result["annualized_return"] is not None
        assert math.isfinite(result["annualized_return"])

    def test_all_metrics_finite_for_valid_sample(self):
        """All metric floats must be finite (not NaN/inf) for a valid sample."""
        returns = make_returns(30, win_rate=0.55)
        result = compute_metrics(returns, holding_days=5)
        assert result["sample_sufficient"] is True
        for key in ["win_rate", "avg_return", "annualized_return", "max_drawdown"]:
            val = result[key]
            if val is not None:
                assert math.isfinite(val), f"{key}={val} is not finite"


# ══════════════════════════════════════════════════════════════════════════════
# format_metrics_report tests
# ══════════════════════════════════════════════════════════════════════════════

class TestFormatMetricsReport:
    def test_no_none_or_nan_in_output(self):
        """Output must never contain literal 'None' or 'nan'."""
        returns = make_returns(20)
        metrics = compute_metrics(returns, holding_days=5)
        report = format_metrics_report(
            metrics=metrics,
            holding_days=5,
            universe_name="tw0050",
            start="2024-01-01",
            end="2024-06-30",
            top_n=5,
        )
        assert "None" not in report, f"'None' found in report:\n{report}"
        assert "nan" not in report.lower(), f"'nan' found in report:\n{report}"

    def test_insufficient_sample_report_contains_warning(self):
        """Insufficient sample report mentions 歷史樣本不足."""
        metrics = compute_metrics([1.0, -1.0], holding_days=5)
        report = format_metrics_report(metrics=metrics, holding_days=5)
        assert "歷史樣本不足" in report

    def test_report_is_string(self):
        """Return type is str."""
        metrics = compute_metrics(make_returns(15), holding_days=5)
        report = format_metrics_report(metrics=metrics, holding_days=5)
        assert isinstance(report, str)
        assert len(report) > 0


# ══════════════════════════════════════════════════════════════════════════════
# _compute_base_score tests
# ══════════════════════════════════════════════════════════════════════════════

class TestComputeBaseScore:
    def test_returns_int_in_range(self):
        """base_score must be an integer in [0, 85]."""
        df = make_ohlcv(60)
        score = _compute_base_score(df)
        assert isinstance(score, int)
        assert 0 <= score <= 85

    def test_uptrend_scores_higher_than_downtrend(self):
        """Uptrend data should score higher than downtrend data."""
        df_up = make_ohlcv(60, trend=0.003)    # strong uptrend
        df_down = make_ohlcv(60, trend=-0.003)  # strong downtrend
        score_up = _compute_base_score(df_up)
        score_down = _compute_base_score(df_down)
        assert score_up > score_down, (
            f"Expected uptrend score ({score_up}) > downtrend score ({score_down})"
        )


# ══════════════════════════════════════════════════════════════════════════════
# run_backtest tests (mocked — no live network calls)
# ══════════════════════════════════════════════════════════════════════════════

class TestRunBacktest:

    def _make_synthetic_history(self, ticker: str, n: int = 80, trend: float = 0.001) -> pd.DataFrame:
        """Return a synthetic DataFrame for mocking yfinance."""
        return make_ohlcv(n, start_price=100.0, trend=trend)

    def test_returns_correct_keys(self):
        """run_backtest result must contain all required keys."""
        required_keys = {
            "trades", "metrics", "report", "holding_days",
            "top_n", "start", "end", "tickers_used",
        }

        # Mock _fetch_full_history to return synthetic data
        with patch("app.backtesting.engine._fetch_full_history") as mock_fetch:
            mock_fetch.return_value = make_ohlcv(100, trend=0.002)

            result = run_backtest(
                tickers=["2330.TW", "2454.TW", "2317.TW"],
                start="2024-01-01",
                end="2024-03-31",
                top_n=2,
                holding_days=5,
                verbose=False,
            )

        assert required_keys.issubset(set(result.keys())), (
            f"Missing keys: {required_keys - set(result.keys())}"
        )

    def test_trades_are_trade_records(self):
        """All entries in trades list must be TradeRecord instances."""
        with patch("app.backtesting.engine._fetch_full_history") as mock_fetch:
            mock_fetch.return_value = make_ohlcv(100, trend=0.002)

            result = run_backtest(
                tickers=["2330.TW", "2454.TW", "2317.TW", "2412.TW", "1301.TW"],
                start="2024-01-01",
                end="2024-04-30",
                top_n=2,
                holding_days=5,
                verbose=False,
            )

        for trade in result["trades"]:
            assert isinstance(trade, TradeRecord)

    def test_report_contains_no_none_or_nan(self):
        """Report string must not contain 'None' or 'nan'."""
        with patch("app.backtesting.engine._fetch_full_history") as mock_fetch:
            mock_fetch.return_value = make_ohlcv(100, trend=0.001)

            result = run_backtest(
                tickers=["2330.TW", "2454.TW", "2317.TW"],
                start="2024-01-01",
                end="2024-03-31",
                top_n=2,
                holding_days=5,
                verbose=False,
            )

        report = result["report"]
        assert "None" not in report, f"'None' in report:\n{report}"
        assert "nan" not in report.lower(), f"'nan' in report:\n{report}"

    def test_no_data_tickers_handled_gracefully(self):
        """If all tickers fail to fetch data, result is empty but valid."""
        with patch("app.backtesting.engine._fetch_full_history") as mock_fetch:
            mock_fetch.return_value = None  # all tickers fail

            result = run_backtest(
                tickers=["2330.TW"],
                start="2024-01-01",
                end="2024-06-30",
                top_n=5,
                holding_days=5,
                verbose=False,
            )

        assert result["trades"] == []
        assert isinstance(result["report"], str)
        assert result["metrics"]["sample_sufficient"] is False

    def test_holding_days_respected(self):
        """holding_days in result matches the input parameter."""
        with patch("app.backtesting.engine._fetch_full_history") as mock_fetch:
            mock_fetch.return_value = make_ohlcv(100)

            result = run_backtest(
                tickers=["2330.TW", "2454.TW"],
                start="2024-01-01",
                end="2024-06-30",
                top_n=1,
                holding_days=10,
                verbose=False,
            )

        assert result["holding_days"] == 10

    def test_small_sample_five_stocks_thirty_days(self):
        """
        The spec requires: 'Small sample (5 stocks, 30 days) runs to completion'.
        This test verifies that with 5 tickers and a ~30-day window, run_backtest
        completes without exception and returns a valid result dict.
        """
        with patch("app.backtesting.engine._fetch_full_history") as mock_fetch:
            mock_fetch.return_value = make_ohlcv(80, trend=0.001)

            result = run_backtest(
                tickers=["2330.TW", "2454.TW", "2317.TW", "2412.TW", "1301.TW"],
                start="2024-01-02",
                end="2024-02-09",   # ~30 trading days
                top_n=3,
                holding_days=5,
                verbose=False,
            )

        assert "trades" in result
        assert "metrics" in result
        assert "report" in result
        assert isinstance(result["report"], str)
        assert result["metrics"]["trade_count"] >= 0


# ══════════════════════════════════════════════════════════════════════════════
# CLI tests
# ══════════════════════════════════════════════════════════════════════════════

class TestCLI:
    def test_missing_start_exits_nonzero(self):
        """--start is required; missing it should raise SystemExit."""
        from scripts.backtest_strategy import parse_args
        with pytest.raises(SystemExit) as exc_info:
            parse_args(["--universe", "tw0050", "--end", "2024-06-30"])
        assert exc_info.value.code != 0

    def test_valid_args_parse_correctly(self):
        """Valid args parse to correct Namespace values."""
        from scripts.backtest_strategy import parse_args
        ns = parse_args([
            "--universe", "tw0050",
            "--start", "2024-01-01",
            "--end", "2024-06-30",
            "--top-n", "5",
            "--holding-days", "5,10",
        ])
        assert ns.universe == "tw0050"
        assert ns.start == "2024-01-01"
        assert ns.end == "2024-06-30"
        assert ns.top_n == 5
        assert ns.holding_days == "5,10"

    def test_main_bad_date_format_exits_nonzero(self):
        """Bad date format should exit with code != 0 (via SystemExit or return value)."""
        from scripts.backtest_strategy import main
        with pytest.raises(SystemExit) as exc_info:
            main(["--start", "not-a-date", "--end", "2024-06-30"])
        assert exc_info.value.code != 0

    def test_main_start_after_end_exits_nonzero(self):
        """start >= end should exit with code != 0 (via SystemExit or return value)."""
        from scripts.backtest_strategy import main
        with pytest.raises(SystemExit) as exc_info:
            main(["--start", "2024-12-01", "--end", "2024-01-01"])
        assert exc_info.value.code != 0

    def test_main_completes_with_mocked_backtest(self):
        """
        Full main() call with mocked run_backtest — should print report and return 0.
        """
        from scripts.backtest_strategy import main
        from app.backtesting.metrics import compute_metrics, format_metrics_report

        mock_returns = make_returns(20)
        mock_metrics = compute_metrics(mock_returns, holding_days=5)
        mock_report = format_metrics_report(
            metrics=mock_metrics, holding_days=5,
            universe_name="tw0050", start="2024-01-01", end="2024-06-30", top_n=5,
        )

        mock_result = {
            "trades": [],
            "metrics": mock_metrics,
            "report": mock_report,
            "holding_days": 5,
            "top_n": 5,
            "start": "2024-01-01",
            "end": "2024-06-30",
            "tickers_used": ["2330.TW"],
        }

        with patch("scripts.backtest_strategy.run_backtest", return_value=mock_result):
            ret = main([
                "--universe", "tw0050",
                "--start", "2024-01-01",
                "--end", "2024-06-30",
                "--top-n", "5",
                "--holding-days", "5",
                "--quiet",
            ])

        assert ret == 0
