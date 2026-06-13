"""
app/backtesting/metrics.py — Trade performance metrics for backtest results.

Computes: trade_count, win_rate, avg_return, annualized_return,
          max_drawdown, sharpe_ratio from a list of trade return values.

All inputs and outputs are plain Python floats — never NaN.
"""

from __future__ import annotations

import math
from typing import Optional


MIN_TRADES_REQUIRED = 10   # below this: return None for all metrics


def compute_metrics(
    returns: list[float],
    holding_days: int = 5,
    trading_days_per_year: int = 252,
) -> dict:
    """
    Compute performance metrics from a list of per-trade return values.

    Parameters
    ----------
    returns : list[float]
        Per-trade return values as percentages (e.g., 3.5 = +3.5%).
        Each value is the return from entry to exit over `holding_days`.
    holding_days : int
        Number of trading days each position is held (used for annualisation).
    trading_days_per_year : int
        Convention; default 252 for Taiwan stock market.

    Returns
    -------
    dict with keys:
        trade_count          : int
        win_rate             : float or None  — fraction of winning trades
        avg_return           : float or None  — mean return across all trades (%)
        annualized_return    : float or None  — approximate annualised return (%)
        max_drawdown         : float or None  — max peak-to-trough drawdown (%)
        sharpe_ratio         : float or None  — simplified Sharpe (mean/std, unscaled)
        sample_sufficient    : bool           — False if trade_count < MIN_TRADES_REQUIRED

    Notes
    -----
    - When sample_sufficient is False all metric fields are None.
    - Sharpe ratio here is mean(returns) / std(returns) — a relative measure,
      not the traditional annualised Sharpe vs risk-free rate.
    """
    n = len(returns)
    if n < MIN_TRADES_REQUIRED:
        return {
            "trade_count": n,
            "win_rate": None,
            "avg_return": None,
            "annualized_return": None,
            "max_drawdown": None,
            "sharpe_ratio": None,
            "sample_sufficient": False,
        }

    # ── Win rate ──────────────────────────────────────────────────────────────
    wins = sum(1 for r in returns if r > 0)
    win_rate = wins / n

    # ── Average return ────────────────────────────────────────────────────────
    avg_return = sum(returns) / n

    # ── Annualised return (simple compounding approximation) ──────────────────
    trades_per_year = trading_days_per_year / max(holding_days, 1)
    # Each trade compounds independently; approximate by compounding mean return
    avg_return_frac = avg_return / 100.0
    annualized_return = ((1.0 + avg_return_frac) ** trades_per_year - 1.0) * 100.0
    if not math.isfinite(annualized_return):
        annualized_return = None

    # ── Max drawdown (equity curve drawdown) ─────────────────────────────────
    # Build cumulative equity curve (starting at 100)
    equity = 100.0
    peak = 100.0
    max_dd = 0.0
    for r in returns:
        equity *= 1.0 + r / 100.0
        if equity > peak:
            peak = equity
        dd = (peak - equity) / peak * 100.0
        if dd > max_dd:
            max_dd = dd
    max_drawdown = max_dd if math.isfinite(max_dd) else None

    # ── Sharpe ratio (simplified: mean / std) ────────────────────────────────
    sharpe_ratio: Optional[float] = None
    if n >= 2:
        mean = avg_return
        variance = sum((r - mean) ** 2 for r in returns) / (n - 1)
        std = math.sqrt(variance) if variance > 0 else 0.0
        if std > 0:
            sharpe_ratio = mean / std
            if not math.isfinite(sharpe_ratio):
                sharpe_ratio = None

    return {
        "trade_count": n,
        "win_rate": win_rate,
        "avg_return": avg_return,
        "annualized_return": annualized_return,
        "max_drawdown": max_drawdown,
        "sharpe_ratio": sharpe_ratio,
        "sample_sufficient": True,
    }


def format_metrics_report(
    metrics: dict,
    holding_days: int,
    universe_name: str = "",
    start: str = "",
    end: str = "",
    top_n: int = 0,
) -> str:
    """
    Format a metrics dict into a human-readable Chinese report string.

    Parameters
    ----------
    metrics       : dict from compute_metrics()
    holding_days  : int
    universe_name : str
    start, end    : YYYY-MM-DD range strings
    top_n         : top-N strategy parameter

    Returns
    -------
    str — multi-line report (print-ready)
    """
    lines: list[str] = []
    lines.append("=" * 50)
    lines.append("回測結果報告")
    lines.append("=" * 50)
    if universe_name:
        lines.append(f"Universe   : {universe_name}")
    if start and end:
        lines.append(f"回測區間   : {start} ~ {end}")
    if top_n:
        lines.append(f"策略       : Top-{top_n} 強勢股，持有 {holding_days} 交易日")
    lines.append("-" * 50)

    n = metrics.get("trade_count", 0)
    lines.append(f"交易筆數   : {n}")

    if not metrics.get("sample_sufficient", False):
        lines.append(f"⚠️  歷史樣本不足（需要 ≥ {MIN_TRADES_REQUIRED} 筆，實際 {n} 筆）")
        lines.append("=" * 50)
        return "\n".join(lines)

    wr = metrics.get("win_rate")
    avg_r = metrics.get("avg_return")
    ann_r = metrics.get("annualized_return")
    mdd = metrics.get("max_drawdown")
    sr = metrics.get("sharpe_ratio")

    lines.append(f"勝率       : {wr * 100:.1f}%" if wr is not None else "勝率       : N/A")
    lines.append(f"平均報酬   : {avg_r:+.2f}%" if avg_r is not None else "平均報酬   : N/A")
    lines.append(f"年化報酬   : {ann_r:+.1f}%" if ann_r is not None else "年化報酬   : N/A")
    lines.append(f"最大回撤   : -{mdd:.1f}%" if mdd is not None else "最大回撤   : N/A")
    lines.append(f"夏普比率   : {sr:.2f}" if sr is not None else "夏普比率   : N/A")
    lines.append("=" * 50)
    lines.append("以上僅為量化回測參考，不構成投資建議。")
    return "\n".join(lines)
