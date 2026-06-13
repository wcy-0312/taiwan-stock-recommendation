"""
ART-004: LINE Notifier — WS-4
Sends a push message via LINE Messaging API using credentials from .env.
Supports a test-message mode to verify credentials work before production use.

Credentials required in .env (project root):
    LINE_CHANNEL_ACCESS_TOKEN=<your channel access token>
    LINE_USER_ID=<your LINE user ID>

Usage (standalone test):
    conda run -n linebot python line_notifier.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path


# ── .env loader (no python-dotenv dependency required) ────────────────────────

def _load_dotenv(env_path: Path) -> None:
    """
    Minimal .env file parser.
    Loads KEY=VALUE pairs into os.environ (skips comments and blank lines).
    Does not override existing environment variables.
    """
    if not env_path.exists():
        return
    with open(env_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value


def _find_env_file() -> Path:
    """
    Search for .env starting from this file's directory, walking up to
    the project root. Returns the first .env found, or raises FileNotFoundError.
    """
    # First, try the project root (two levels above artifacts/checkpoint-2/ART-004/)
    candidate_dirs = [
        Path(__file__).parent,                              # ART-004/
        Path(__file__).parent.parent.parent.parent,        # project root
        Path(__file__).parent.parent.parent.parent.parent, # one more up (safety)
        Path.cwd(),
    ]
    for d in candidate_dirs:
        env_file = d / ".env"
        if env_file.exists():
            return env_file
    raise FileNotFoundError(
        ".env file not found. Create one at the project root with:\n"
        "  LINE_CHANNEL_ACCESS_TOKEN=<token>\n"
        "  LINE_USER_ID=<user_id>"
    )


def load_credentials() -> tuple[str, str]:
    """
    Load LINE credentials from .env.

    Returns
    -------
    (channel_access_token, user_id)

    Raises
    ------
    FileNotFoundError  — if .env is missing
    ValueError         — if required keys are absent or empty
    """
    try:
        env_path = _find_env_file()
        _load_dotenv(env_path)
        print(f"[line_notifier] Loaded credentials from: {env_path}")
    except FileNotFoundError as exc:
        raise FileNotFoundError(str(exc)) from exc

    token = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN", "").strip()
    user_id = os.environ.get("LINE_USER_ID", "").strip()

    missing = []
    if not token:
        missing.append("LINE_CHANNEL_ACCESS_TOKEN")
    if not user_id:
        missing.append("LINE_USER_ID")

    if missing:
        raise ValueError(
            f"Missing required .env variable(s): {', '.join(missing)}\n"
            "See .env.example for the correct format."
        )

    return token, user_id


# ── LINE API push message ──────────────────────────────────────────────────────

def send_push_message(text: str, token: str, user_id: str) -> dict:
    """
    Send a plain-text push message via LINE Messaging API.

    Uses line-bot-sdk 3.7.0 (already installed in linebot env).

    Parameters
    ----------
    text    : str — the message body
    token   : str — LINE channel access token
    user_id : str — recipient LINE user ID

    Returns
    -------
    dict with keys: success (bool), status_code (int), error (str|None)
    """
    try:
        from linebot.v3 import WebhookHandler  # noqa: F401 (import check)
        from linebot.v3.messaging import (
            ApiClient,
            Configuration,
            MessagingApi,
            PushMessageRequest,
            TextMessage,
        )
    except ImportError:
        # Fallback: try line-bot-sdk v2 API style
        try:
            from linebot import LineBotApi
            from linebot.models import TextSendMessage
            api = LineBotApi(token)
            api.push_message(user_id, TextSendMessage(text=text))
            print("[line_notifier] Message sent via line-bot-sdk v2 API.")
            return {"success": True, "status_code": 200, "error": None}
        except Exception as exc2:
            return {"success": False, "status_code": -1, "error": str(exc2)}

    try:
        config = Configuration(access_token=token)
        with ApiClient(config) as api_client:
            messaging_api = MessagingApi(api_client)
            request = PushMessageRequest(
                to=user_id,
                messages=[TextMessage(text=text)],
            )
            messaging_api.push_message(push_message_request=request)

        print("[line_notifier] Message sent successfully via LINE Messaging API (v3).")
        return {"success": True, "status_code": 200, "error": None}

    except Exception as exc:
        err_msg = str(exc)
        print(f"[line_notifier] ERROR sending message: {err_msg}")
        return {"success": False, "status_code": -1, "error": err_msg}


def send_recommendation_message(text: str) -> dict:
    """
    Convenience wrapper: load credentials then send text.

    Parameters
    ----------
    text : str — formatted LINE message (from recommendation_generator)

    Returns
    -------
    dict with keys: success, status_code, error
    """
    token, user_id = load_credentials()
    return send_push_message(text, token, user_id)


# ── Smoke test ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=== line_notifier smoke test ===\n")

    # Step 1: Verify credentials are loadable
    try:
        token, user_id = load_credentials()
        print(f"[OK] Credentials loaded.")
        print(f"     TOKEN = {'*' * (len(token) - 4)}{token[-4:] if len(token) >= 4 else '****'}")
        print(f"     USER_ID = {user_id[:4]}{'*' * max(0, len(user_id) - 4)}")
    except (FileNotFoundError, ValueError) as exc:
        print(f"[FAIL] Credential load failed:\n  {exc}")
        print("\nCreate a .env file at the project root with:")
        print("  LINE_CHANNEL_ACCESS_TOKEN=<your token>")
        print("  LINE_USER_ID=<your LINE user ID>")
        sys.exit(1)

    # Step 2: Send test message
    test_message = (
        "【台股智能推薦系統 - 測試訊息】\n"
        "LINE 通知功能已成功連線。\n"
        "每日推薦將於週一至週五上午 08:30 推送。"
    )

    print(f"\nSending test message to user {user_id[:4]}***...")
    result = send_push_message(test_message, token, user_id)

    if result["success"]:
        print("\n[PASS] line_notifier smoke test complete — message sent successfully.")
    else:
        print(f"\n[FAIL] Message send failed: {result['error']}")
        sys.exit(1)
