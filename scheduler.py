"""
ART-005: Scheduler — WS-5
Orchestrates the full Taiwan stock recommendation pipeline using APScheduler.

Schedule (CST = Asia/Taipei = UTC+8):
  - Job 1 (analysis):  every weekday at 14:00 CST — fetch data, run analysis,
                        generate recommendations, cache the formatted message
  - Job 2 (send):      every weekday at 08:30 CST — send cached LINE message

Pipeline dependency order:
    ART-001 data_pipeline  →  ART-002 analysis_engine
    →  ART-003 recommendation_generator  →  ART-004 line_notifier

Usage:
    conda run -n linebot python scheduler.py              # run scheduler daemon
    conda run -n linebot python scheduler.py --dry-run   # run full pipeline once immediately
    conda run -n linebot python scheduler.py --send-now  # send cached message now
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from datetime import date, datetime
from pathlib import Path

# ── Environment setup ──────────────────────────────────────────────────────────
# Windows console may default to GBK; force UTF-8 for Chinese output
os.environ.setdefault("PYTHONIOENCODING", "utf-8")

# Reconfigure stdout/stderr to UTF-8 if running on Windows
if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    try:
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")
    except Exception:
        pass  # non-fatal; best-effort

# ── Path setup — locate upstream modules ─────────────────────────────────────
_THIS_DIR = Path(__file__).parent.resolve()
_ARTIFACTS_ROOT = _THIS_DIR.parent.parent  # artifacts/
_ART001_PATH = str(_ARTIFACTS_ROOT / "checkpoint-1" / "ART-001")
_ART002_PATH = str(_ARTIFACTS_ROOT / "checkpoint-1" / "ART-002")
_ART003_PATH = str(_ARTIFACTS_ROOT / "checkpoint-2" / "ART-003")
_ART004_PATH = str(_ARTIFACTS_ROOT / "checkpoint-2" / "ART-004")

for _p in [_ART001_PATH, _ART002_PATH, _ART003_PATH, _ART004_PATH]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

# ── Cache file for the formatted LINE message ─────────────────────────────────
_CACHE_DIR = _THIS_DIR / ".scheduler-cache"
_CACHE_DIR.mkdir(exist_ok=True)
_MESSAGE_CACHE_FILE = _CACHE_DIR / "pending-message.json"

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger("scheduler")


# ── Message cache helpers ─────────────────────────────────────────────────────

def _save_message(message: str, run_date: str) -> None:
    """Persist formatted LINE message to local JSON cache."""
    payload = {
        "message": message,
        "run_date": run_date,
        "saved_at": datetime.now().isoformat(),
    }
    with open(_MESSAGE_CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    logger.info(f"Message cached to: {_MESSAGE_CACHE_FILE}")


def _load_message() -> dict | None:
    """Load cached message. Returns dict with 'message' and 'run_date', or None."""
    if not _MESSAGE_CACHE_FILE.exists():
        logger.warning("No cached message found at: %s", _MESSAGE_CACHE_FILE)
        return None
    try:
        with open(_MESSAGE_CACHE_FILE, encoding="utf-8") as f:
            return json.load(f)
    except Exception as exc:
        logger.error("Failed to read message cache: %s", exc)
        return None


def _clear_message_cache() -> None:
    """Remove the cached message after a successful send."""
    if _MESSAGE_CACHE_FILE.exists():
        _MESSAGE_CACHE_FILE.unlink()
        logger.info("Message cache cleared.")


# ── Pipeline stages ───────────────────────────────────────────────────────────

def run_analysis_pipeline() -> None:
    """
    Job 1 — Analysis (runs at 14:00 CST on weekdays).

    Steps:
      1. Fetch OHLCV data for all 0050 tickers (ART-001)
      2. Compute technical analysis signals (ART-002)
      3. Select top 3–5 recommendations and format LINE message (ART-003)
      4. Cache the formatted message for Job 2 to send
    """
    logger.info("=== Analysis pipeline started ===")

    run_date = date.today().isoformat()

    # Step 1: Data
    try:
        from data_pipeline import fetch_universe, TAIWAN_0050_TICKERS
    except ImportError as exc:
        logger.error("Cannot import data_pipeline (ART-001): %s", exc)
        return

    logger.info("Fetching data for %d tickers...", len(TAIWAN_0050_TICKERS))
    data = fetch_universe(tickers=TAIWAN_0050_TICKERS, days=60)
    if not data:
        logger.error("data_pipeline returned no data — aborting analysis run.")
        return
    logger.info("Data fetched: %d/%d tickers succeeded.", len(data), len(TAIWAN_0050_TICKERS))

    # Step 2: Analysis
    try:
        from analysis_engine import analyse_universe
    except ImportError as exc:
        logger.error("Cannot import analysis_engine (ART-002): %s", exc)
        return

    logger.info("Running technical analysis...")
    analyses = analyse_universe(data)
    logger.info("Analysis complete: %d stocks analysed.", len(analyses))

    # Step 3: Recommendations + message formatting
    try:
        from recommendation_generator import generate_recommendations
    except ImportError as exc:
        logger.error("Cannot import recommendation_generator (ART-003): %s", exc)
        return

    recommendations, message = generate_recommendations(analyses, run_date=run_date)
    logger.info(
        "Recommendations selected: %d stocks (labels: %s)",
        len(recommendations),
        [r.label for r in recommendations],
    )

    # Step 4: Cache message
    _save_message(message, run_date)
    logger.info("=== Analysis pipeline complete — message cached for 08:30 send. ===")


def run_send_pipeline() -> None:
    """
    Job 2 — LINE Send (runs at 08:30 CST on weekdays).

    Loads the cached message from Job 1 and sends it via LINE Messaging API.
    """
    logger.info("=== LINE send job started ===")

    cached = _load_message()
    if cached is None:
        logger.error("No cached message available. Was the analysis job run first?")
        return

    message_text = cached.get("message", "")
    run_date = cached.get("run_date", "unknown")

    if not message_text:
        logger.error("Cached message is empty — aborting send.")
        return

    logger.info("Sending LINE message for analysis date: %s", run_date)

    # Import LINE notifier
    try:
        from line_notifier import send_recommendation_message
    except ImportError as exc:
        logger.error("Cannot import line_notifier (ART-004): %s", exc)
        return

    # Send
    result = send_recommendation_message(message_text)

    if result.get("success"):
        logger.info("LINE message sent successfully.")
        _clear_message_cache()
    else:
        logger.error(
            "LINE send failed (status=%s): %s",
            result.get("status_code"),
            result.get("error"),
        )


# ── Dry-run (manual full pipeline) ────────────────────────────────────────────

def run_dry_run() -> None:
    """
    Run the full pipeline end-to-end immediately (no schedule).
    Used for testing and the Checkpoint 3 acceptance dry-run.
    """
    logger.info("=== DRY RUN: Full pipeline (analysis + LINE send) ===")
    logger.info("Step 1/2: Running analysis pipeline...")
    run_analysis_pipeline()

    logger.info("Step 2/2: Running LINE send...")
    run_send_pipeline()

    logger.info("=== DRY RUN complete ===")


# ── Scheduler setup ───────────────────────────────────────────────────────────

def build_scheduler():
    """
    Build and configure the APScheduler BlockingScheduler.

    Jobs:
      - analysis_job : Mon–Fri at 14:00 Asia/Taipei
      - send_job     : Mon–Fri at 08:30 Asia/Taipei (sends previous day's analysis)
    """
    try:
        from apscheduler.schedulers.blocking import BlockingScheduler
        from apscheduler.triggers.cron import CronTrigger
    except ImportError as exc:
        logger.error("APScheduler not installed. Run: conda run -n linebot pip install apscheduler")
        raise

    scheduler = BlockingScheduler(timezone="Asia/Taipei")

    # Job 1: Analysis at 14:00 CST weekdays
    scheduler.add_job(
        run_analysis_pipeline,
        trigger=CronTrigger(
            day_of_week="mon-fri",
            hour=14,
            minute=0,
            timezone="Asia/Taipei",
        ),
        id="analysis_job",
        name="Daily analysis pipeline (14:00 CST)",
        misfire_grace_time=300,   # allow up to 5 minutes late start
        coalesce=True,            # skip duplicate firings if machine was asleep
    )

    # Job 2: LINE send at 08:30 CST weekdays
    scheduler.add_job(
        run_send_pipeline,
        trigger=CronTrigger(
            day_of_week="mon-fri",
            hour=8,
            minute=30,
            timezone="Asia/Taipei",
        ),
        id="send_job",
        name="Daily LINE send (08:30 CST)",
        misfire_grace_time=300,
        coalesce=True,
    )

    return scheduler


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Taiwan Stock Recommendation Scheduler (ART-005)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run the full pipeline once immediately (analysis + LINE send) and exit.",
    )
    parser.add_argument(
        "--send-now",
        action="store_true",
        help="Send the cached LINE message immediately and exit (skip analysis).",
    )
    parser.add_argument(
        "--analysis-now",
        action="store_true",
        help="Run the analysis pipeline immediately and cache the message (skip send).",
    )
    args = parser.parse_args()

    if args.dry_run:
        run_dry_run()
        return

    if args.send_now:
        run_send_pipeline()
        return

    if args.analysis_now:
        run_analysis_pipeline()
        return

    # Default: start the scheduler daemon
    logger.info("Starting Taiwan Stock Recommendation Scheduler...")
    logger.info("  Analysis job : Mon-Fri 14:00 CST (Asia/Taipei)")
    logger.info("  Send job     : Mon-Fri 08:30 CST (Asia/Taipei)")
    logger.info("Press Ctrl+C to stop.")

    scheduler = build_scheduler()
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Scheduler stopped.")


if __name__ == "__main__":
    main()
