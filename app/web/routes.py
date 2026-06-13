"""
app/web/routes.py — FastAPI router for web dashboard endpoints.

V4 changes:
  - Uses app.cache.latest_cache module (holiday-safe, not limited to today)
  - Adds /api/stock/{code}/history endpoint (yfinance + MA/RSI/MACD, async Plotly)
  - Dashboard includes market_events sidebar from data/market_events/latest.json
  - yfinance failure returns HTTP 200 + {error: "..."} (DL-3)
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates

from app.cache.latest_cache import (
    load_latest_analysis_cache,
    get_latest_analysis_date,
    find_stock_in_latest_cache,
    list_latest_results,
)

logger = logging.getLogger(__name__)

router = APIRouter()

_TEMPLATES_DIR = Path(__file__).parent.parent.parent / "templates"
templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))

_MARKET_EVENTS_PATH = Path(__file__).parent.parent.parent / "data" / "market_events" / "latest.json"


# ── Market events helper ──────────────────────────────────────────────────────

def _load_market_events() -> list[dict]:
    """Load market events from data/market_events/latest.json."""
    try:
        if not _MARKET_EVENTS_PATH.exists():
            return []
        with _MARKET_EVENTS_PATH.open(encoding="utf-8") as fh:
            data = json.load(fh)
        return data.get("events", [])[:5]
    except Exception as exc:
        logger.warning("_load_market_events: %s", exc)
        return []


# ── Web routes ────────────────────────────────────────────────────────────────

@router.get("/", response_class=HTMLResponse, include_in_schema=False)
async def home(request: Request):
    return templates.TemplateResponse(request=request, name="home.html")


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    cache = load_latest_analysis_cache()
    data_date = get_latest_analysis_date()
    market_events = _load_market_events()

    if cache is None:
        return templates.TemplateResponse(
            request=request, name="dashboard.html",
            context={"no_data": True, "data_date": data_date, "market_events": market_events},
        )
    results = cache.get("results", [])
    market_stats = cache.get("market_stats", {})
    strong = [r for r in results if r.get("direction") == "bullish"]
    weak = [r for r in results if r.get("direction") == "bearish"]
    neutral = [r for r in results if r.get("direction") == "neutral"]
    return templates.TemplateResponse(
        request=request, name="dashboard.html",
        context={
            "no_data": False,
            "data_date": data_date,
            "market_stats": market_stats,
            "strong": sorted(strong, key=lambda r: r.get("radar_score", 0), reverse=True)[:10],
            "weak": sorted(weak, key=lambda r: r.get("radar_score", 0))[:10],
            "neutral": sorted(neutral, key=lambda r: r.get("radar_score", 0), reverse=True)[:5],
            "total": len(results),
            "market_events": market_events,
        },
    )


@router.get("/watchlist", response_class=HTMLResponse)
async def watchlist_page(request: Request, token: str = ""):
    """Token-based watchlist page.

    Flow: LINE Bot generates a short-lived token (app.tokens.create_token),
    sends it in a Flex Message link.  This route validates the token and
    renders the user's watchlist without requiring LIFF or LINE Login.

    No token → show instructions.
    Invalid/expired token → show expiry message.
    Valid token → show watchlist with radar data.
    """
    from app.tokens import validate_token
    from app.linebot.watchlist import get_watchlist

    if not token:
        return templates.TemplateResponse(
            request=request, name="watchlist.html",
            context={"state": "no_token"},
        )

    user_id = validate_token(token)
    if not user_id:
        return templates.TemplateResponse(
            request=request, name="watchlist.html",
            context={"state": "expired"},
        )

    tickers = get_watchlist(user_id)
    data_date = get_latest_analysis_date()
    stocks = []
    for ticker in tickers:
        normalized = ticker if ticker.endswith(".TW") else ticker + ".TW"
        result = find_stock_in_latest_cache(normalized)
        code = ticker.replace(".TW", "")
        if result:
            stocks.append({
                "code": code,
                "name": result.get("name", ""),
                "radar_score": result.get("radar_score", 0),
                "direction": result.get("direction", "neutral"),
                "confidence": result.get("confidence", "低"),
                "latest_close": result.get("latest_close", 0),
                "price_change_1d_pct": result.get("price_change_1d_pct", 0),
                "data_date": result.get("data_date", data_date),
                "has_data": True,
            })
        else:
            stocks.append({"code": code, "has_data": False})

    return templates.TemplateResponse(
        request=request, name="watchlist.html",
        context={
            "state": "ok",
            "stocks": stocks,
            "data_date": data_date,
            "count": len(stocks),
        },
    )


@router.get("/search", response_class=HTMLResponse)
async def search_page(request: Request):
    """Stock search page — entry point from Rich Menu 查詢個股 URI action."""
    results = list_latest_results()
    strong = sorted(
        [r for r in results if r.get("direction") == "bullish"],
        key=lambda r: r.get("radar_score", 0), reverse=True,
    )[:5]
    weak = sorted(
        [r for r in results if r.get("direction") == "bearish"],
        key=lambda r: r.get("radar_score", 0),
    )[:5]
    hot_stocks = [
        {"code": "2330", "name": "台積電"},
        {"code": "2317", "name": "鴻海"},
        {"code": "2454", "name": "聯發科"},
        {"code": "2412", "name": "中華電"},
        {"code": "2891", "name": "中信金"},
    ]
    return templates.TemplateResponse(
        request=request, name="search.html",
        context={
            "hot_stocks": hot_stocks,
            "strong_top5": strong,
            "weak_top5": weak,
            "data_date": get_latest_analysis_date(),
            "total": len(results),
        },
    )


@router.get("/stock/{code}", response_class=HTMLResponse)
async def stock_page(request: Request, code: str):
    code = code.upper().replace("-", ".")
    if not code.endswith(".TW"):
        code = code + ".TW"
    data_date = get_latest_analysis_date()
    market_events = _load_market_events()

    result = find_stock_in_latest_cache(code)
    if result is None:
        return templates.TemplateResponse(
            request=request, name="stock.html",
            context={
                "no_data": True,
                "code": code.replace(".TW", ""),
                "data_date": data_date,
                "market_events": market_events,
            },
        )
    return templates.TemplateResponse(
        request=request, name="stock.html",
        context={
            "no_data": False,
            "code": code.replace(".TW", ""),
            "data_date": data_date,
            "result": result,
            "market_events": market_events,
        },
    )


# ── JSON API routes ───────────────────────────────────────────────────────────


@router.get("/api/radar/latest")
async def api_radar_latest():
    cache = load_latest_analysis_cache()
    if cache is None:
        return JSONResponse({"error": "no data available", "results": [], "market_stats": {}})
    results = cache.get("results", [])
    safe_results = []
    for r in results:
        safe_results.append({
            "ticker": r.get("ticker", ""),
            "code": r.get("code", ""),
            "name": r.get("name", ""),
            "data_date": r.get("data_date", ""),
            "radar_score": r.get("radar_score", 0),
            "direction": r.get("direction", "neutral"),
            "confidence": r.get("confidence", "低"),
            "latest_close": r.get("latest_close", 0),
            "price_change_1d_pct": r.get("price_change_1d_pct", 0),
            "trend_score": r.get("trend_score", 0),
            "momentum_score": r.get("momentum_score", 0),
            "volume_score": r.get("volume_score", 0),
            "risk_score": r.get("risk_score", 0),
            "market_score": r.get("market_score", 0),
        })
    return JSONResponse({
        "data_date": get_latest_analysis_date(),
        "market_stats": cache.get("market_stats", {}),
        "results": safe_results,
    })


@router.get("/api/stock/{code}")
async def api_stock(code: str):
    code = code.upper()
    if not code.endswith(".TW"):
        code = code + ".TW"
    result = find_stock_in_latest_cache(code)
    if result is None:
        return JSONResponse({"error": f"{code} not found in latest radar"}, status_code=404)
    return JSONResponse(dict(result))


@router.get("/api/stock/{code}/history")
async def api_stock_history(code: str, days: int = 120):
    """
    Return OHLCV + technical indicators for Plotly chart rendering.

    yfinance failure returns HTTP 200 + {"error": "..."} (DL-3).
    """
    code = code.upper()
    if not code.endswith(".TW"):
        code = code + ".TW"

    try:
        import yfinance as yf
        import pandas as pd

        # Use period="6mo" to avoid holiday-counting issues (DL-3)
        df = yf.download(code, period="6mo", auto_adjust=True, progress=False)
        if df is None or df.empty:
            return JSONResponse({"error": "無法取得歷史資料，請稍後再試"})

        # Flatten MultiIndex columns if present (yfinance sometimes returns them)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = [col[0] for col in df.columns]

        # Ensure required columns
        required = {"Close", "Open", "High", "Low", "Volume"}
        if not required.issubset(df.columns):
            return JSONResponse({"error": "資料格式錯誤，請稍後再試"})

        # Compute technical indicators
        close = df["Close"]

        # Moving averages
        ma5 = close.rolling(5).mean()
        ma20 = close.rolling(20).mean()
        ma60 = close.rolling(60).mean()

        # RSI(14)
        delta = close.diff()
        gain = delta.where(delta > 0, 0.0).rolling(14).mean()
        loss = (-delta).where(delta < 0, 0.0).rolling(14).mean()
        rs = gain / loss.replace(0, float("nan"))
        rsi = 100 - (100 / (1 + rs))

        # MACD(12, 26, 9)
        ema12 = close.ewm(span=12, adjust=False).mean()
        ema26 = close.ewm(span=26, adjust=False).mean()
        macd = ema12 - ema26
        macd_signal = macd.ewm(span=9, adjust=False).mean()
        macd_hist = macd - macd_signal

        def _safe_list(series) -> list:
            """Convert pandas Series to JSON-safe list (NaN → None)."""
            return [
                None if (x != x or x is None) else round(float(x), 4)
                for x in series
            ]

        dates = [d.strftime("%Y-%m-%d") for d in df.index]

        return JSONResponse({
            "ticker": code,
            "dates": dates,
            "close": _safe_list(df["Close"]),
            "open": _safe_list(df["Open"]),
            "high": _safe_list(df["High"]),
            "low": _safe_list(df["Low"]),
            "volume": _safe_list(df["Volume"]),
            "ma5": _safe_list(ma5),
            "ma20": _safe_list(ma20),
            "ma60": _safe_list(ma60),
            "rsi": _safe_list(rsi),
            "macd": _safe_list(macd),
            "macd_signal": _safe_list(macd_signal),
            "macd_hist": _safe_list(macd_hist),
        })

    except Exception as exc:
        logger.warning("api_stock_history: failed for %s — %s", code, exc)
        return JSONResponse({"error": "無法取得歷史資料，請稍後再試"})
