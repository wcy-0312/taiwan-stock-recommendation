"""
app/main.py — FastAPI application + APScheduler in one process.

Entry point for Render deployment:
    uvicorn app.main:app --host 0.0.0.0 --port $PORT

Or run directly:
    python -m app.main

Schedule (CST = Asia/Taipei = UTC+8):
    - Analysis job : Mon-Fri 14:00 CST — run_analysis() + cache results
    - Push job     : Mon-Fri 08:30 CST — push cached LINE broadcast messages

Routes:
    GET  /health   — Render health check
    POST /webhook  — LINE Messaging API webhook
"""

from __future__ import annotations

import logging
import os
import sys
from contextlib import asynccontextmanager
from datetime import datetime
from typing import AsyncIterator

from fastapi import FastAPI

# ── Logging setup (before any other imports so format is consistent) ─────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

# ── Load .env if present (development convenience; Render uses real env vars) ─
def _load_dotenv_if_present() -> None:
    """Load .env from the project root into os.environ if it exists."""
    from pathlib import Path
    env_path = Path(__file__).parent.parent / ".env"
    if not env_path.exists():
        return
    with open(env_path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            os.environ.setdefault(key.strip(), val.strip().strip('"').strip("'"))


_load_dotenv_if_present()

# ── Warn early if PUBLIC_BASE_URL is missing ─────────────────────────────────
def _check_public_base_url() -> None:
    from app.config import PUBLIC_BASE_URL
    if not PUBLIC_BASE_URL:
        logger.warning(
            "PUBLIC_BASE_URL not set — LINE links will be broken. "
            "Set PUBLIC_BASE_URL to your Render URL (e.g. https://your-app.onrender.com)."
        )
    else:
        logger.info("[main] PUBLIC_BASE_URL = %s", PUBLIC_BASE_URL)


_check_public_base_url()

# ── Scheduler setup ───────────────────────────────────────────────────────────

_scheduler = None


def _run_analysis_job() -> None:
    """
    Daily analysis job (14:00 CST).
    Runs the full analysis pipeline and caches results + LINE messages.
    """
    logger.info("=== [scheduler] Analysis job started ===")
    try:
        from app.pipeline import run_analysis, generate_line_messages, cache_analysis_results
        from app.config import CACHE_DIR

        today = datetime.today().strftime("%Y-%m-%d")
        all_results, selection, market_stats = run_analysis()

        # Cache full analysis
        cache_analysis_results(all_results, market_stats, today)

        # Cache LINE messages separately for push job
        messages = generate_line_messages(selection, market_stats, today)
        _save_pending_messages(messages, today)

        logger.info(
            "=== [scheduler] Analysis job complete — %d messages cached ===",
            len(messages),
        )
    except Exception as exc:
        logger.error("=== [scheduler] Analysis job FAILED: %s ===", exc, exc_info=True)


def _run_push_job() -> None:
    """
    Daily push job (08:30 CST).
    Loads cached LINE messages and pushes to LINE_USER_ID.
    """
    logger.info("=== [scheduler] Push job started ===")
    try:
        from app.linebot.notifier import send_broadcast

        messages, data_date = _load_pending_messages()
        if not messages:
            logger.warning("[scheduler] No pending messages to send.")
            return

        logger.info("[scheduler] Sending %d messages for %s", len(messages), data_date)
        result = send_broadcast(messages)
        if result.get("success"):
            logger.info("=== [scheduler] Push job complete ===")
            _clear_pending_messages()
        else:
            logger.error(
                "=== [scheduler] Push job FAILED: status=%s error=%s ===",
                result.get("status_code"),
                result.get("error"),
            )
    except Exception as exc:
        logger.error("=== [scheduler] Push job FAILED: %s ===", exc, exc_info=True)


# ── Pending-message cache helpers ─────────────────────────────────────────────

def _pending_messages_path():
    from pathlib import Path
    from app.config import CACHE_DIR
    return CACHE_DIR / "pending_messages.json"


def _save_pending_messages(messages: list[str], data_date: str) -> None:
    import json
    path = _pending_messages_path()
    payload = {
        "data_date": data_date,
        "messages": messages,
        "saved_at": datetime.now().isoformat(),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)
    logger.info("[main] Pending messages saved to %s", path)


def _load_pending_messages() -> tuple[list[str], str]:
    import json
    path = _pending_messages_path()
    if not path.exists():
        return [], ""
    try:
        with path.open(encoding="utf-8") as fh:
            data = json.load(fh)
        return data.get("messages", []), data.get("data_date", "")
    except Exception as exc:
        logger.error("[main] Failed to load pending messages: %s", exc)
        return [], ""


def _clear_pending_messages() -> None:
    path = _pending_messages_path()
    if path.exists():
        path.unlink()
        logger.info("[main] Pending messages cleared")


# ── Lifespan: start/stop scheduler ───────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Start APScheduler on startup, stop on shutdown."""
    global _scheduler
    try:
        from apscheduler.schedulers.background import BackgroundScheduler
        from apscheduler.triggers.cron import CronTrigger

        _scheduler = BackgroundScheduler(timezone="Asia/Taipei")

        # Analysis: Mon-Fri 14:00 CST
        _scheduler.add_job(
            _run_analysis_job,
            trigger=CronTrigger(
                day_of_week="mon-fri",
                hour=14,
                minute=0,
                timezone="Asia/Taipei",
            ),
            id="analysis_job",
            name="Daily analysis (14:00 CST)",
            misfire_grace_time=300,
            coalesce=True,
        )

        # Push: Mon-Fri 08:30 CST
        _scheduler.add_job(
            _run_push_job,
            trigger=CronTrigger(
                day_of_week="mon-fri",
                hour=8,
                minute=30,
                timezone="Asia/Taipei",
            ),
            id="push_job",
            name="Daily LINE push (08:30 CST)",
            misfire_grace_time=300,
            coalesce=True,
        )

        _scheduler.start()
        logger.info("[main] APScheduler started (analysis 14:00, push 08:30 CST)")

    except ImportError:
        logger.warning("[main] APScheduler not installed — scheduler disabled")
        _scheduler = None

    yield

    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        logger.info("[main] APScheduler stopped")


# ── FastAPI application ───────────────────────────────────────────────────────

app = FastAPI(
    title="台股智能雷達",
    description="Taiwan stock radar LINE Bot — daily broadcasts + interactive commands",
    version="4.0.0",
    lifespan=lifespan,
)

# Mount webhook router
from app.linebot.webhook import router as webhook_router  # noqa: E402
app.include_router(webhook_router)

# Mount web dashboard router
from app.web.routes import router as web_router  # noqa: E402
app.include_router(web_router)


# ── Direct run (python -m app.main) ──────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", 8000))
    logger.info("[main] Starting uvicorn on port %d", port)
    uvicorn.run("app.main:app", host="0.0.0.0", port=port, log_level="info")
