"""
scripts/backtest_strategy.py — Walk-forward backtesting CLI.

Usage
-----
    python scripts/backtest_strategy.py \\
        --universe tw0050 \\
        --start 2024-01-01 \\
        --end 2026-06-13 \\
        --top-n 5 \\
        --holding-days 5

Options
-------
    --universe      Universe name (default: tw0050)
    --start         Backtest start date YYYY-MM-DD (required)
    --end           Backtest end date   YYYY-MM-DD (default: today)
    --top-n         Top-N stocks to select per rebalance cycle (default: 5)
    --holding-days  Comma-separated holding periods in trading days (default: 5)
                    Multiple values run separate backtests, e.g. --holding-days 5,10,20
    --rebalance     Rebalance frequency in trading days (default: same as holding-days)
    --verbose       Print detailed progress (default: True)
    --quiet         Suppress progress output
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

# ── Make sure the project root is on sys.path ──────────────────────────────
_PROJECT_ROOT = Path(__file__).parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from app.data.universe_provider import get_tickers
from app.backtesting.engine import run_backtest


def parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Taiwan Stock Radar — Walk-Forward Backtest CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--universe",
        default="tw0050",
        help="Universe name (default: tw0050)",
    )
    parser.add_argument(
        "--start",
        required=True,
        help="Backtest start date YYYY-MM-DD",
    )
    parser.add_argument(
        "--end",
        default=datetime.today().strftime("%Y-%m-%d"),
        help="Backtest end date YYYY-MM-DD (default: today)",
    )
    parser.add_argument(
        "--top-n",
        type=int,
        default=5,
        help="Top-N stocks to select per rebalance (default: 5)",
    )
    parser.add_argument(
        "--holding-days",
        default="5",
        help="Holding period(s) in trading days; comma-separated for multiple runs (default: 5)",
    )
    parser.add_argument(
        "--rebalance",
        type=int,
        default=None,
        help="Rebalance frequency in trading days (default: same as holding-days)",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress progress output",
    )
    return parser.parse_args(argv)


def validate_date(date_str: str, label: str) -> None:
    try:
        datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        print(f"ERROR: {label} must be YYYY-MM-DD, got: {date_str!r}", file=sys.stderr)
        sys.exit(1)


def main(argv=None) -> int:
    args = parse_args(argv)
    verbose = not args.quiet

    # ── Validate dates ────────────────────────────────────────────────────────
    validate_date(args.start, "--start")
    validate_date(args.end, "--end")

    if args.start >= args.end:
        print("ERROR: --start must be before --end", file=sys.stderr)
        sys.exit(1)

    # ── Parse holding-days ────────────────────────────────────────────────────
    try:
        holding_days_list = [int(h.strip()) for h in args.holding_days.split(",")]
    except ValueError:
        print(
            f"ERROR: --holding-days must be comma-separated integers, got: {args.holding_days!r}",
            file=sys.stderr,
        )
        sys.exit(1)

    if any(h < 1 for h in holding_days_list):
        print("ERROR: all --holding-days values must be >= 1", file=sys.stderr)
        sys.exit(1)

    if args.top_n < 1:
        print("ERROR: --top-n must be >= 1", file=sys.stderr)
        sys.exit(1)

    # ── Load universe ─────────────────────────────────────────────────────────
    if verbose:
        print(f"Loading universe: {args.universe} ...")

    try:
        tickers = get_tickers(args.universe)
    except FileNotFoundError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)

    if verbose:
        print(f"Universe: {len(tickers)} tickers")

    # ── Run backtest(s) ───────────────────────────────────────────────────────
    any_error = False

    for holding_days in holding_days_list:
        rebalance_every = args.rebalance if args.rebalance is not None else holding_days

        if verbose and len(holding_days_list) > 1:
            print(f"\n{'=' * 60}")
            print(f"Running backtest: holding_days={holding_days}")
            print(f"{'=' * 60}")

        try:
            result = run_backtest(
                tickers=tickers,
                start=args.start,
                end=args.end,
                top_n=args.top_n,
                holding_days=holding_days,
                rebalance_every=rebalance_every,
                verbose=verbose,
            )
        except Exception as exc:
            print(f"ERROR: backtest failed for holding_days={holding_days}: {exc}", file=sys.stderr)
            any_error = True
            continue

        print("\n" + result["report"])

        # Print trade summary if verbose
        if verbose:
            trades = result.get("trades", [])
            if trades:
                print(f"\n首 5 筆交易明細 (共 {len(trades)} 筆):")
                for trade in trades[:5]:
                    sign = "+" if trade.return_pct >= 0 else ""
                    print(
                        f"  {trade.ticker:10s}  入場 {trade.entry_date}  "
                        f"出場 {trade.exit_date}  "
                        f"報酬 {sign}{trade.return_pct:.2f}%"
                    )

    return 1 if any_error else 0


if __name__ == "__main__":
    sys.exit(main())
