"""
scheduler.py — Backward-compatibility wrapper for V2 app.main pipeline.

This file is preserved for backward-compatibility per ICR-5.
The full implementation is now in app/main.py (FastAPI + APScheduler).

Usage (unchanged from V1):
    python scheduler.py                 # start scheduler daemon (redirects to app.main)
    python scheduler.py --dry-run       # run full pipeline immediately and exit
    python scheduler.py --send-now      # send cached LINE messages and exit
    python scheduler.py --analysis-now  # run analysis and cache result, then exit

All flags delegate directly to app.pipeline and app.linebot.notifier.
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

# ── Environment setup ──────────────────────────────────────────────────────────
os.environ.setdefault("PYTHONIOENCODING", "utf-8")

if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    try:
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")
    except Exception:
        pass

# ── Load .env if present ───────────────────────────────────────────────────────
_PROJECT_ROOT = Path(__file__).parent.resolve()


def _load_dotenv() -> None:
    env_path = _PROJECT_ROOT / ".env"
    if not env_path.exists():
        return
    with open(env_path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            os.environ.setdefault(key.strip(), val.strip().strip('"').strip("'"))


_load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("scheduler")


# ── Pipeline wrappers ─────────────────────────────────────────────────────────

def run_analysis_pipeline() -> None:
    """Run the V2 analysis pipeline and cache results."""
    logger.info("=== Analysis pipeline started (V2 via app.pipeline) ===")
    try:
        from app.pipeline import run_analysis, generate_line_messages, cache_analysis_results
        from app.config import CACHE_DIR

        today = datetime.today().strftime("%Y-%m-%d")
        all_results, selection, market_stats = run_analysis()
        cache_analysis_results(all_results, market_stats, today)

        messages = generate_line_messages(selection, market_stats, today)
        # Save pending messages for send job
        import json
        pending_path = CACHE_DIR / "pending_messages.json"
        pending_path.parent.mkdir(parents=True, exist_ok=True)
        with pending_path.open("w", encoding="utf-8") as fh:
            json.dump(
                {"data_date": today, "messages": messages, "saved_at": datetime.now().isoformat()},
                fh,
                ensure_ascii=False,
                indent=2,
            )
        logger.info(
            "=== Analysis pipeline complete — %d messages cached for 08:30 send. ===",
            len(messages),
        )
    except Exception as exc:
        logger.error("=== Analysis pipeline FAILED: %s ===", exc, exc_info=True)
        raise


def run_send_pipeline() -> None:
    """Load cached LINE messages and push them."""
    logger.info("=== LINE send job started (V2 via app.linebot.notifier) ===")
    try:
        from app.config import CACHE_DIR
        from app.linebot.notifier import send_broadcast
        import json

        pending_path = CACHE_DIR / "pending_messages.json"
        if not pending_path.exists():
            logger.error("No cached messages found. Run --analysis-now first.")
            return

        with pending_path.open(encoding="utf-8") as fh:
            data = json.load(fh)

        messages = data.get("messages", [])
        data_date = data.get("data_date", "unknown")

        if not messages:
            logger.error("Cached messages list is empty — aborting send.")
            return

        logger.info("Sending %d messages for %s", len(messages), data_date)
        result = send_broadcast(messages)

        if result.get("success"):
            logger.info("=== LINE send complete ===")
            pending_path.unlink()
        else:
            logger.error(
                "=== LINE send FAILED: status=%s error=%s ===",
                result.get("status_code"),
                result.get("error"),
            )
    except Exception as exc:
        logger.error("=== LINE send FAILED: %s ===", exc, exc_info=True)
        raise


def run_dry_run() -> None:
    """Run analysis + send pipeline immediately."""
    logger.info("=== DRY RUN: Full pipeline (analysis + LINE send) ===")
    run_analysis_pipeline()
    run_send_pipeline()
    logger.info("=== DRY RUN complete ===")


# ── Scheduler daemon ──────────────────────────────────────────────────────────

def start_scheduler_daemon() -> None:
    """Start the APScheduler daemon (delegates to app.main scheduler logic)."""
    logger.info("Starting Taiwan Stock Radar Scheduler daemon...")
    logger.info("  Analysis job : Mon-Fri 14:00 CST (Asia/Taipei)")
    logger.info("  Send job     : Mon-Fri 08:30 CST (Asia/Taipei)")
    logger.info("  (Tip: use `uvicorn app.main:app` for the full FastAPI + scheduler)")

    try:
        from apscheduler.schedulers.blocking import BlockingScheduler
        from apscheduler.triggers.cron import CronTrigger
    except ImportError:
        logger.error("APScheduler not installed. Run: pip install apscheduler")
        sys.exit(1)

    scheduler = BlockingScheduler(timezone="Asia/Taipei")

    scheduler.add_job(
        run_analysis_pipeline,
        trigger=CronTrigger(day_of_week="mon-fri", hour=14, minute=0, timezone="Asia/Taipei"),
        id="analysis_job",
        name="Daily analysis (14:00 CST)",
        misfire_grace_time=300,
        coalesce=True,
    )
    scheduler.add_job(
        run_send_pipeline,
        trigger=CronTrigger(day_of_week="mon-fri", hour=8, minute=30, timezone="Asia/Taipei"),
        id="send_job",
        name="Daily LINE send (08:30 CST)",
        misfire_grace_time=300,
        coalesce=True,
    )

    logger.info("Press Ctrl+C to stop.")
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Scheduler stopped.")


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Taiwan Stock Radar Scheduler — backward-compat wrapper (V2)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run full pipeline once immediately (analysis + LINE send) and exit.",
    )
    parser.add_argument(
        "--send-now",
        action="store_true",
        help="Send cached LINE messages immediately and exit.",
    )
    parser.add_argument(
        "--analysis-now",
        action="store_true",
        help="Run analysis pipeline immediately, cache results, then exit.",
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

    # Default: start daemon
    start_scheduler_daemon()


if __name__ == "__main__":
    main()
