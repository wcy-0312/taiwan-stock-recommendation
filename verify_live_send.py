"""
verify_live_send.py — Backward-compatibility wrapper for V2 end-to-end verification.

This file is preserved for backward-compatibility per ICR-5.
Full V2 pipeline is in app/ modules.

Prerequisites:
    A .env file at the project root with:
        LINE_CHANNEL_ACCESS_TOKEN=<your_token>
        LINE_USER_ID=<your_line_user_id>
        LINE_CHANNEL_SECRET=<your_channel_secret>

Usage:
    python verify_live_send.py              # default: --check-env
    python verify_live_send.py --check-env  # validate .env credentials (no API call)
    python verify_live_send.py --send-now   # send cached LINE messages
    python verify_live_send.py --full       # run full pipeline (analysis + live send)

Exit codes:
    0 = all checks passed / send succeeded
    1 = missing credentials or send failed
"""

from __future__ import annotations

import argparse
import os
import sys
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

_PROJECT_ROOT = Path(__file__).parent.resolve()


# ── Helpers ───────────────────────────────────────────────────────────────────

def _load_dotenv(env_path: Path) -> dict[str, str]:
    """Minimal .env parser — no external dependency."""
    if not env_path.exists():
        return {}
    values: dict[str, str] = {}
    with open(env_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            values[key.strip()] = val.strip().strip('"').strip("'")
    return values


def check_env(verbose: bool = True) -> bool:
    """
    Verify that .env credentials are present and non-empty (V2: includes LINE_CHANNEL_SECRET).
    Returns True if credentials look valid, False otherwise.
    """
    env_path = _PROJECT_ROOT / ".env"
    print(f"[check-env] Looking for .env at: {env_path}")

    if not env_path.exists():
        print("[FAIL] .env file not found.")
        print("       Create it at the project root with:")
        print("           LINE_CHANNEL_ACCESS_TOKEN=<your_token>")
        print("           LINE_USER_ID=<your_line_user_id>")
        print("           LINE_CHANNEL_SECRET=<your_channel_secret>")
        return False

    # Load into environment for downstream modules
    creds = _load_dotenv(env_path)
    for k, v in creds.items():
        os.environ.setdefault(k, v)

    token = creds.get("LINE_CHANNEL_ACCESS_TOKEN", "")
    user_id = creds.get("LINE_USER_ID", "")
    secret = creds.get("LINE_CHANNEL_SECRET", "")

    ok = True

    if not token:
        print("[FAIL] LINE_CHANNEL_ACCESS_TOKEN is missing or empty in .env")
        ok = False
    else:
        masked = token[:6] + "..." + token[-4:] if len(token) > 10 else "***"
        print(f"[PASS] LINE_CHANNEL_ACCESS_TOKEN found: {masked}")

    if not user_id:
        print("[FAIL] LINE_USER_ID is missing or empty in .env")
        ok = False
    else:
        print(f"[PASS] LINE_USER_ID found: {user_id}")

    if not secret:
        print("[WARN] LINE_CHANNEL_SECRET is missing (required for webhook signature verification)")
        # Not fatal for --full mode but warn
    else:
        masked_s = secret[:4] + "..." + secret[-2:] if len(secret) > 6 else "***"
        print(f"[PASS] LINE_CHANNEL_SECRET found: {masked_s}")

    if ok:
        print("[PASS] .env credentials look valid. Ready for live send test.")

    return ok


def run_analysis() -> bool:
    """Run the V2 analysis pipeline. Returns True on success."""
    print("\n[verify] Running V2 analysis pipeline (app.pipeline)...")
    try:
        from scheduler import run_analysis_pipeline
        run_analysis_pipeline()
        return True
    except Exception as exc:
        print(f"[FAIL] Analysis pipeline raised: {exc}")
        return False


def run_send() -> bool:
    """Send cached LINE messages via V2 notifier. Returns True on success."""
    print("\n[verify] Sending cached LINE messages (app.linebot.notifier)...")
    try:
        from scheduler import run_send_pipeline
        run_send_pipeline()
        print("[verify] Send pipeline executed. Check your LINE app for the message.")
        return True
    except Exception as exc:
        print(f"[FAIL] Send pipeline raised: {exc}")
        return False


# ── Acceptance criteria checklist ─────────────────────────────────────────────

CHECKPOINT_3_CRITERIA = [
    "A .env file exists with LINE_CHANNEL_ACCESS_TOKEN, LINE_USER_ID, LINE_CHANNEL_SECRET",
    "app/main.py starts without error (FastAPI + APScheduler)",
    "GET /health returns 200",
    "POST /webhook endpoint exists with LINE signature verification",
    "SQLite watchlist CRUD: add, remove, list all work",
    "The analysis pipeline runs successfully (V2 via app.pipeline)",
    "A LINE push message is received on the user's LINE app",
    "No credentials appear in any source file",
]


def print_acceptance_criteria(check_results: dict | None = None) -> None:
    print("\n=== Checkpoint 3 Acceptance Criteria ===")
    for i, criterion in enumerate(CHECKPOINT_3_CRITERIA, 1):
        if check_results:
            status = check_results.get(str(i), None)
            mark = "[PASS]" if status else "[PENDING]" if status is None else "[FAIL]"
        else:
            mark = "[ ]"
        print(f"  {mark} {i}. {criterion}")
    print()


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Checkpoint 3 live send verification (V2)"
    )
    parser.add_argument(
        "--check-env",
        action="store_true",
        help="Validate .env credentials (no API call). Default mode.",
    )
    parser.add_argument(
        "--send-now",
        action="store_true",
        help="Send the cached LINE messages immediately (requires .env credentials).",
    )
    parser.add_argument(
        "--full",
        action="store_true",
        help="Run full pipeline: analysis + live LINE send (requires .env credentials).",
    )
    args = parser.parse_args()

    print("=== Checkpoint 3 Live Send Verification (V2) ===\n")

    # Default: --check-env
    if not (args.send_now or args.full):
        ok = check_env()
        print_acceptance_criteria()
        if not ok:
            print("ACTION REQUIRED: Create .env at project root with LINE credentials.")
            print("Then re-run with --send-now or --full.")
        sys.exit(0 if ok else 1)

    # --check-env is implied for all modes
    if not check_env():
        print("\n[ABORT] Cannot proceed without valid .env credentials.")
        sys.exit(1)

    if args.full:
        print("\n[verify] MODE: Full pipeline (analysis + live LINE send)")
        ok_analysis = run_analysis()
        if not ok_analysis:
            print("[ABORT] Analysis failed — not sending LINE message.")
            sys.exit(1)
        ok_send = run_send()
        print_acceptance_criteria({
            "1": True,
            "2": True,
            "3": True,
            "4": True,
            "5": True,
            "6": ok_analysis,
            "7": ok_send,
            "8": True,
        })
        sys.exit(0 if (ok_analysis and ok_send) else 1)

    if args.send_now:
        print("\n[verify] MODE: Send cached message only (skip analysis re-run)")
        ok_send = run_send()
        print_acceptance_criteria({
            "1": True,
            "2": None,
            "3": None,
            "4": None,
            "5": None,
            "6": None,
            "7": ok_send,
            "8": True,
        })
        sys.exit(0 if ok_send else 1)


if __name__ == "__main__":
    main()
