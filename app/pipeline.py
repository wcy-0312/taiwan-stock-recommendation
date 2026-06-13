"""
app/pipeline.py — Main analysis pipeline.

Orchestrates: data → features → scoring → recommendation

This is the central entry point for both the scheduler and the LINE Bot.
Backward-compatible with old scheduler.py --analysis-now and verify_live_send.py.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Optional

from app.config import CACHE_DIR, YFINANCE_HISTORY_DAYS, YFINANCE_BATCH_DELAY
from app.data.universe_provider import get_universe, get_ticker_map
from app.data.yfinance_provider import fetch_universe_ohlcv
from app.features.technical import compute_technical_features
from app.features.volume import compute_volume_features
from app.features.risk import compute_risk_features
from app.scoring.radar import score_stock
from app.scoring.reasons import (
    build_positive_reasons,
    build_negative_reasons,
    build_risk_notes,
    build_invalidation_conditions,
)
from app.scoring.market_context import compute_market_score, compute_market_context_stats
from app.scoring.models import StockRadarResult
from app.recommendation.selector import run_selection, SelectionResult
from app.recommendation.formatter import build_broadcast_messages


def run_analysis(
    universe_name: str = "tw0050",
    fetch_date: Optional[str] = None,
) -> tuple[list[StockRadarResult], SelectionResult, dict]:
    """
    Run the full analysis pipeline for a universe.

    Parameters
    ----------
    universe_name : str   — universe to analyse (default: "tw0050")
    fetch_date    : str   — YYYY-MM-DD cache key (default: today)

    Returns
    -------
    (all_results, selection, market_stats)
        all_results  : list[StockRadarResult] sorted by radar_score desc
        selection    : SelectionResult with strong/weak/turning categories
        market_stats : dict from compute_market_context_stats()
    """
    if fetch_date is None:
        fetch_date = datetime.today().strftime("%Y-%m-%d")

    print(f"[pipeline] Starting analysis — universe={universe_name}, date={fetch_date}")

    # ── 1. Load universe ──────────────────────────────────────────────────────
    universe = get_universe(universe_name)
    ticker_map = get_ticker_map(universe_name)
    tickers = [entry["ticker"] for entry in universe]
    print(f"[pipeline] Universe: {len(tickers)} tickers")

    # ── 2. Fetch OHLCV ───────────────────────────────────────────────────────
    ohlcv_data = fetch_universe_ohlcv(
        tickers,
        days=YFINANCE_HISTORY_DAYS,
        fetch_date=fetch_date,
        batch_delay=YFINANCE_BATCH_DELAY,
    )
    print(f"[pipeline] Fetched OHLCV for {len(ohlcv_data)} tickers")

    # ── 3. Compute features for all stocks ───────────────────────────────────
    stock_features: list[tuple[str, dict, dict, dict, str, float, float, float]] = []

    for ticker, ohlcv_result in ohlcv_data.items():
        df = ohlcv_result["df"]
        data_date = ohlcv_result["latest_data_date"]

        try:
            feats_tech = compute_technical_features(df)
            feats_vol = compute_volume_features(df)
            feats_risk = compute_risk_features(df)

            close_series = df["Close"].astype(float)
            latest_close = float(close_series.iloc[-1]) if not close_series.empty else 0.0

            # Price changes
            price_change_1d = 0.0
            price_change_5d = 0.0
            if len(close_series) >= 2:
                prev = float(close_series.iloc[-2])
                if prev > 0:
                    price_change_1d = (latest_close - prev) / prev * 100
            if len(close_series) >= 6:
                prev5 = float(close_series.iloc[-6])
                if prev5 > 0:
                    price_change_5d = (latest_close - prev5) / prev5 * 100

            stock_features.append((
                ticker, feats_tech, feats_vol, feats_risk,
                data_date, latest_close, price_change_1d, price_change_5d,
            ))

        except Exception as exc:
            print(f"[pipeline] ERROR computing features for {ticker}: {exc}")
            continue

    # ── 4. First pass: compute base_scores for market context ─────────────────
    # We need a preliminary pass to compute market_score before final scoring
    prelim_base_scores: list[int] = []
    for ticker, feats_tech, feats_vol, feats_risk, *_ in stock_features:
        from app.scoring.radar import (
            compute_trend_score, compute_momentum_score,
            compute_volume_score, compute_risk_score,
        )
        t = compute_trend_score(feats_tech)
        m = compute_momentum_score(feats_tech)
        v = compute_volume_score(feats_vol)
        r = compute_risk_score(feats_risk)
        prelim_base_scores.append(t + m + v + r)

    market_stats = compute_market_context_stats(prelim_base_scores)
    market_score = market_stats["market_score"]
    print(
        f"[pipeline] Market stats — bullish: {market_stats['bullish_count']}/"
        f"{market_stats['universe_size']}, market_score: {market_score}"
    )

    # ── 5. Second pass: full scoring with market_score ────────────────────────
    raw_results: list[StockRadarResult] = []
    for ticker, feats_tech, feats_vol, feats_risk, data_date, latest_close, chg_1d, chg_5d in stock_features:
        info = ticker_map.get(ticker, {})
        code = info.get("code", ticker.replace(".TW", ""))
        name = info.get("name", code)

        pos_reasons = build_positive_reasons(feats_tech, feats_vol, feats_risk)
        neg_reasons = build_negative_reasons(feats_tech, feats_vol, feats_risk)
        risk_notes = build_risk_notes(feats_tech, feats_vol, feats_risk)
        inval_conds = build_invalidation_conditions(feats_tech, feats_risk)

        result = score_stock(
            ticker=ticker,
            code=code,
            name=name,
            latest_close=latest_close,
            price_change_1d_pct=chg_1d,
            price_change_5d_pct=chg_5d,
            data_date=data_date,
            feats_technical=feats_tech,
            feats_volume=feats_vol,
            feats_risk=feats_risk,
            market_score=market_score,
            positive_reasons=pos_reasons,
            negative_reasons=neg_reasons,
            risk_notes=risk_notes,
            invalidation_conditions=inval_conds,
            rank_in_universe=0,       # filled in after sorting
            universe_size=len(stock_features),
        )
        raw_results.append(result)

    # ── 6. Sort and assign ranks ──────────────────────────────────────────────
    raw_results.sort(key=lambda r: r.radar_score, reverse=True)
    for rank, result in enumerate(raw_results, start=1):
        result.rank_in_universe = rank
        result.universe_size = len(raw_results)

    # ── 7. Run selection ─────────────────────────────────────────────────────
    selection = run_selection(raw_results)
    print(
        f"[pipeline] Selection — strong: {len(selection.strong_watchlist)}, "
        f"weak: {len(selection.weakness_alerts)}, "
        f"turning: {len(selection.turning_points)}"
    )

    return raw_results, selection, market_stats


def generate_line_messages(
    selection: SelectionResult,
    market_stats: dict,
    data_date: str,
) -> list[str]:
    """
    Generate LINE broadcast messages from a SelectionResult.

    Parameters
    ----------
    selection   : SelectionResult from run_selection()
    market_stats: dict from compute_market_context_stats()
    data_date   : YYYY-MM-DD string

    Returns
    -------
    list[str] — up to 3 message strings
    """
    return build_broadcast_messages(
        strong_stocks=selection.broadcast_strong,
        weak_stocks=selection.broadcast_weak,
        market_stats=market_stats,
        data_date=data_date,
    )


def cache_analysis_results(
    results: list[StockRadarResult],
    market_stats: dict,
    data_date: str,
) -> Path:
    """
    Persist analysis results to data/cache/ as JSON.

    Parameters
    ----------
    results     : list[StockRadarResult]
    market_stats: dict
    data_date   : YYYY-MM-DD string

    Returns
    -------
    Path to the written cache file.
    """
    cache_path = CACHE_DIR / f"analysis_{data_date}.json"

    def _result_to_dict(r: StockRadarResult) -> dict:
        return {
            "ticker": r.ticker,
            "code": r.code,
            "name": r.name,
            "data_date": r.data_date,
            "latest_close": r.latest_close,
            "price_change_1d_pct": r.price_change_1d_pct,
            "price_change_5d_pct": r.price_change_5d_pct,
            "radar_score": r.radar_score,
            "rank_in_universe": r.rank_in_universe,
            "universe_size": r.universe_size,
            "direction": r.direction,
            "confidence": r.confidence,
            "trend_score": r.trend_score,
            "momentum_score": r.momentum_score,
            "volume_score": r.volume_score,
            "risk_score": r.risk_score,
            "market_score": r.market_score,
            "chip_score": r.chip_score,
            "ma5": r.ma5,
            "ma20": r.ma20,
            "ma60": r.ma60,
            "rsi14": r.rsi14,
            "macd_hist": r.macd_hist,
            "macd_hist_delta": r.macd_hist_delta,
            "volume_ratio": r.volume_ratio,
            "atr14": r.atr14,
            "atr_pct": r.atr_pct,
            "support_20d": r.support_20d,
            "resistance_20d": r.resistance_20d,
            "positive_reasons": r.positive_reasons,
            "negative_reasons": r.negative_reasons,
            "risk_notes": r.risk_notes,
            "invalidation_conditions": r.invalidation_conditions,
            "historical_win_rate_5d": r.historical_win_rate_5d,
            "historical_avg_return_5d": r.historical_avg_return_5d,
            "historical_win_rate_10d": r.historical_win_rate_10d,
            "historical_avg_return_10d": r.historical_avg_return_10d,
        }

    payload = {
        "data_date": data_date,
        "generated_at": datetime.now().isoformat(),
        "market_stats": market_stats,
        "results": [_result_to_dict(r) for r in results],
    }

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    with cache_path.open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)

    print(f"[pipeline] Analysis cached to {cache_path}")
    return cache_path


def load_cached_analysis(data_date: str) -> Optional[dict]:
    """
    Load a previously cached analysis from data/cache/.

    Parameters
    ----------
    data_date : str — YYYY-MM-DD

    Returns
    -------
    dict or None if not found
    """
    cache_path = CACHE_DIR / f"analysis_{data_date}.json"
    if not cache_path.exists():
        return None
    try:
        with cache_path.open(encoding="utf-8") as fh:
            return json.load(fh)
    except Exception as exc:
        print(f"[pipeline] WARNING: failed to load cache {cache_path}: {exc}")
        return None
