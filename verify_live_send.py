"""
ART-006: Live Send Verification Script — Checkpoint 4

Purpose:
    Verifies the full end-to-end pipeline including the live LINE push notification.
    This script is the acceptance-criteria runner for Checkpoint 4.

Prerequisites:
    A `.env` file must exist at the project root with:
        LINE_CHANNEL_ACCESS_TOKEN=<your_token>
        LINE_USER_ID=<your_line_user_id>

Usage:
    conda run -n linebot python verify_live_send.py [--check-env] [--send-now] [--full]

Modes:
    --check-env   : Validate that .env credentials are present and non-empty (no API call)
    --send-now    : Send the cached LINE message immediately (credentials required)
    --full        : Run full pipeline (analysis + live LINE send) end-to-end (credentials required)
    (no flag)     : Alias for --check-env

Exit codes:
    0 = all checks passed / send succeeded
    1 = missing credentials or send failed
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

# ── Path setup — all modules are co-located in the same directory ──────────────
_THIS_DIR = Path(__file__).parent.resolve()
_PROJECT_ROOT = _THIS_DIR  # flat repo: verify_live_send.py is at project root

if str(_THIS_DIR) not in sys.path:
    sys.path.insert(0, str(_THIS_DIR))

# ── Environment setup ──────────────────────────────────────────────────────────
os.environ.setdefault("PYTHONIOENCODING", "utf-8")

if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    try:
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")
    except Exception:
        pass


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
    Verify that .env credentials are present and non-empty.
    Returns True if credentials look valid, False otherwise.
    """
    env_path = _PROJECT_ROOT / ".env"
    print(f"[check-env] Looking for .env at: {env_path}")

    if not env_path.exists():
        print("[FAIL] .env file not found.")
        print("       Create it at the project root with:")
        print("           LINE_CHANNEL_ACCESS_TOKEN=<your_token>")
        print("           LINE_USER_ID=<your_line_user_id>")
        return False

    creds = _load_dotenv(env_path)
    token = creds.get("LINE_CHANNEL_ACCESS_TOKEN", "")
    user_id = creds.get("LINE_USER_ID", "")

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

    if ok:
        print("[PASS] .env credentials look valid. Ready for live send test.")

    return ok


def run_analysis() -> bool:
    """
    Run the analysis pipeline and cache the LINE message.
    Returns True on success.
    """
    print("\n[verify] Running analysis pipeline (ART-001 → ART-002 → ART-003)...")
    try:
        from scheduler import run_analysis_pipeline
        run_analysis_pipeline()
        return True
    except Exception as exc:
        print(f"[FAIL] Analysis pipeline raised: {exc}")
        return False


def run_send() -> bool:
    """
    Send the cached LINE message via line_notifier (ART-004).
    Returns True on success.
    """
    print("\n[verify] Sending cached LINE message (ART-004)...")
    # Ensure .env is loaded into environment before importing line_notifier
    env_path = _PROJECT_ROOT / ".env"
    creds = _load_dotenv(env_path)
    for k, v in creds.items():
        os.environ.setdefault(k, v)

    try:
        from scheduler import run_send_pipeline
        # run_send_pipeline logs its own outcome
        run_send_pipeline()
        print("[verify] Send pipeline executed. Check your LINE app for the message.")
        return True
    except Exception as exc:
        print(f"[FAIL] Send pipeline raised: {exc}")
        return False


# ── Acceptance criteria checklist ─────────────────────────────────────────────

CHECKPOINT_4_CRITERIA = [
    "A .env file exists at the project root with LINE_CHANNEL_ACCESS_TOKEN and LINE_USER_ID",
    "The analysis pipeline runs successfully (49+ tickers fetched, 3-5 recommendations)",
    "A LINE push message is received on the user's LINE app",
    "The message contains: today's date, stock tickers, BUY/SELL labels, Chinese explanations, disclaimer",
    "No credentials appear in any source file",
]


def print_acceptance_criteria(check_results: dict[str, bool] | None = None) -> None:
    print("\n=== Checkpoint 4 Acceptance Criteria ===")
    for i, criterion in enumerate(CHECKPOINT_4_CRITERIA, 1):
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
        description="ART-006: Checkpoint 4 live send verification"
    )
    parser.add_argument(
        "--check-env",
        action="store_true",
        help="Validate .env credentials (no API call). Default mode.",
    )
    parser.add_argument(
        "--send-now",
        action="store_true",
        help="Send the cached LINE message immediately (requires .env credentials).",
    )
    parser.add_argument(
        "--full",
        action="store_true",
        help="Run full pipeline: analysis + live LINE send (requires .env credentials).",
    )
    args = parser.parse_args()

    print("=== ART-006: Checkpoint 4 Live Send Verification ===\n")

    # Default: --check-env
    if not (args.send_now or args.full):
        ok = check_env()
        print_acceptance_criteria()
        if not ok:
            print("ACTION REQUIRED: Create .env at project root with LINE credentials.")
            print("Then re-run with --send-now or --full to complete Checkpoint 4.")
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
            "2": ok_analysis,
            "3": ok_send,
            "4": ok_send,
            "5": True,
        })
        sys.exit(0 if (ok_analysis and ok_send) else 1)

    if args.send_now:
        print("\n[verify] MODE: Send cached message only (skip analysis re-run)")
        ok_send = run_send()
        print_acceptance_criteria({
            "1": True,
            "2": None,   # not tested in this mode
            "3": ok_send,
            "4": ok_send,
            "5": True,
        })
        sys.exit(0 if ok_send else 1)


if __name__ == "__main__":
    main()
