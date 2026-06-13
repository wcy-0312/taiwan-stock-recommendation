"""
app/web/routes.py — FastAPI router for web dashboard endpoints.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates

logger = logging.getLogger(__name__)

router = APIRouter()

_TEMPLATES_DIR = Path(__file__).parent.parent.parent / "templates"
logger.info("templates dir: %s (exists=%s)", _TEMPLATES_DIR, _TEMPLATES_DIR.exists())
try:
    templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))
except Exception as _e:
    logger.error("Jinja2Templates init failed: %s", _e)
    templates = None

_CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache"


def _load_latest_cache() -> Optional[dict]:
    """Load the most recent analysis cache file."""
    try:
        files = sorted(_CACHE_DIR.glob("analysis_*.json"), reverse=True)
        if not files:
            return None
        with files[0].open(encoding="utf-8") as fh:
            return json.load(fh)
    except Exception as exc:
        logger.warning("_load_latest_cache: %s", exc)
        return None


def _get_cache_date() -> str:
    files = sorted((_CACHE_DIR).glob("analysis_*.json"), reverse=True) if _CACHE_DIR.exists() else []
    if files:
        return files[0].stem.replace("analysis_", "")
    return "—"


@router.get("/", response_class=HTMLResponse, include_in_schema=False)
async def home(request: Request):
    if templates is None:
        return HTMLResponse(f"<pre>Templates not initialized. Dir: {_TEMPLATES_DIR} exists={_TEMPLATES_DIR.exists()}</pre>", status_code=500)
    try:
        return templates.TemplateResponse("home.html", {"request": request})
    except Exception as exc:
        logger.error("/: template error: %s", exc, exc_info=True)
        return HTMLResponse(f"<pre>Template error: {exc}</pre>", status_code=500)


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    cache = _load_latest_cache()
    data_date = _get_cache_date()
    if cache is None:
        return templates.TemplateResponse("dashboard.html", {
            "request": request,
            "no_data": True,
            "data_date": data_date,
        })
    results = cache.get("results", [])
    market_stats = cache.get("market_stats", {})
    strong = [r for r in results if r.get("direction") == "bullish"]
    weak = [r for r in results if r.get("direction") == "bearish"]
    neutral = [r for r in results if r.get("direction") == "neutral"]
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "no_data": False,
        "data_date": data_date,
        "market_stats": market_stats,
        "strong": sorted(strong, key=lambda r: r.get("radar_score", 0), reverse=True)[:10],
        "weak": sorted(weak, key=lambda r: r.get("radar_score", 0))[:10],
        "neutral": sorted(neutral, key=lambda r: r.get("radar_score", 0), reverse=True)[:5],
        "total": len(results),
    })


@router.get("/stock/{code}", response_class=HTMLResponse)
async def stock_page(request: Request, code: str):
    code = code.upper().replace("-", ".")
    if not code.endswith(".TW"):
        code = code + ".TW"
    cache = _load_latest_cache()
    data_date = _get_cache_date()
    if cache is None:
        return templates.TemplateResponse("stock.html", {
            "request": request,
            "no_data": True,
            "code": code,
            "data_date": data_date,
        })
    result = next((r for r in cache.get("results", []) if r.get("ticker", "").upper() == code.upper()), None)
    if result is None:
        return templates.TemplateResponse("stock.html", {
            "request": request,
            "no_data": True,
            "code": code,
            "data_date": data_date,
        })
    return templates.TemplateResponse("stock.html", {
        "request": request,
        "no_data": False,
        "code": code.replace(".TW", ""),
        "data_date": data_date,
        "result": result,
    })


@router.get("/api/radar/latest")
async def api_radar_latest():
    cache = _load_latest_cache()
    if cache is None:
        return JSONResponse({"error": "no data available", "results": [], "market_stats": {}})
    results = cache.get("results", [])
    # Strip internal fields, keep only display-safe fields
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
        "data_date": _get_cache_date(),
        "market_stats": cache.get("market_stats", {}),
        "results": safe_results,
    })


@router.get("/api/stock/{code}")
async def api_stock(code: str):
    code = code.upper()
    if not code.endswith(".TW"):
        code = code + ".TW"
    cache = _load_latest_cache()
    if cache is None:
        raise HTTPException(status_code=404, detail="No data available")
    result = next((r for r in cache.get("results", []) if r.get("ticker", "").upper() == code.upper()), None)
    if result is None:
        raise HTTPException(status_code=404, detail=f"{code} not found in latest radar")
    # Return full result but exclude any internal implementation details
    safe = dict(result)
    return JSONResponse(safe)
