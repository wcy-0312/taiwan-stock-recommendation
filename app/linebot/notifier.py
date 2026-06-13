"""
app/linebot/notifier.py — LINE Messaging API push/reply client.

Sends messages to a single user or reply to a webhook event.
Credentials are loaded from app.config (which reads from environment / .env).

API reference: https://developers.line.biz/en/reference/messaging-api/
"""

from __future__ import annotations

import json
import logging
import urllib.request
import urllib.error
from typing import Optional

import os

logger = logging.getLogger(__name__)

# Lazy credential accessors — read at call time so .env loaded after import works
def _get_access_token() -> str:
    return os.environ.get("LINE_CHANNEL_ACCESS_TOKEN", "")

def _get_user_id() -> str:
    return os.environ.get("LINE_USER_ID", "")

_PUSH_URL = "https://api.line.me/v2/bot/message/push"
_REPLY_URL = "https://api.line.me/v2/bot/message/reply"

# Maximum number of messages per push/reply call allowed by LINE API
_LINE_API_MAX_MESSAGES = 5


def _make_text_message(text: str) -> dict:
    """Wrap a plain text string in LINE TextMessage format."""
    return {"type": "text", "text": text}


def _build_headers() -> dict:
    return {
        "Content-Type": "application/json; charset=UTF-8",
        "Authorization": f"Bearer {_get_access_token()}",
    }


def push_messages(messages: list[str], user_id: Optional[str] = None) -> dict:
    """
    Push one or more text messages to a LINE user.

    Parameters
    ----------
    messages : list[str] — list of message strings (max 5 per LINE API call)
    user_id  : str       — LINE user ID to push to; defaults to LINE_USER_ID from config

    Returns
    -------
    dict with keys:
        success    : bool
        status_code: int
        error      : str or None
    """
    target_user = user_id or _get_user_id()
    if not target_user:
        logger.error("push_messages: no user_id provided and LINE_USER_ID not configured")
        return {"success": False, "status_code": 0, "error": "no user_id"}

    if not _get_access_token():
        logger.error("push_messages: LINE_CHANNEL_ACCESS_TOKEN not configured")
        return {"success": False, "status_code": 0, "error": "no access token"}

    if not messages:
        logger.warning("push_messages: no messages to send")
        return {"success": True, "status_code": 200, "error": None}

    # Send in batches of _LINE_API_MAX_MESSAGES
    results = []
    for batch_start in range(0, len(messages), _LINE_API_MAX_MESSAGES):
        batch = messages[batch_start : batch_start + _LINE_API_MAX_MESSAGES]
        result = _push_batch(target_user, batch)
        results.append(result)
        if not result["success"]:
            return result  # abort on first failure

    return results[-1] if results else {"success": True, "status_code": 200, "error": None}


def _push_batch(user_id: str, messages: list[str]) -> dict:
    """Push a single batch of up to 5 messages."""
    payload = {
        "to": user_id,
        "messages": [_make_text_message(m) for m in messages],
    }
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        _PUSH_URL,
        data=body,
        headers=_build_headers(),
        method="POST",
    )
    try:
        with urllib.request.urlopen(req) as resp:
            status = resp.status
            logger.info("push_messages: sent %d messages, status=%d", len(messages), status)
            return {"success": True, "status_code": status, "error": None}
    except urllib.error.HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="replace")
        logger.error(
            "push_messages: HTTP %d — %s",
            exc.code,
            error_body[:500],
        )
        return {"success": False, "status_code": exc.code, "error": error_body[:500]}
    except Exception as exc:
        logger.error("push_messages: unexpected error — %s", exc)
        return {"success": False, "status_code": 0, "error": str(exc)}


def reply_messages(reply_token: str, messages: list[str]) -> dict:
    """
    Reply to a LINE webhook event using a reply token.

    Parameters
    ----------
    reply_token : str      — token from the webhook event (valid for ~30 s)
    messages    : list[str] — up to 5 reply message strings

    Returns
    -------
    dict with keys: success, status_code, error
    """
    if not _get_access_token():
        logger.error("reply_messages: LINE_CHANNEL_ACCESS_TOKEN not configured")
        return {"success": False, "status_code": 0, "error": "no access token"}

    if not reply_token:
        logger.error("reply_messages: no reply_token provided")
        return {"success": False, "status_code": 0, "error": "no reply_token"}

    batch = messages[:_LINE_API_MAX_MESSAGES]
    payload = {
        "replyToken": reply_token,
        "messages": [_make_text_message(m) for m in batch],
    }
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        _REPLY_URL,
        data=body,
        headers=_build_headers(),
        method="POST",
    )
    try:
        with urllib.request.urlopen(req) as resp:
            status = resp.status
            logger.info("reply_messages: replied %d messages, status=%d", len(batch), status)
            return {"success": True, "status_code": status, "error": None}
    except urllib.error.HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="replace")
        logger.error(
            "reply_messages: HTTP %d — %s",
            exc.code,
            error_body[:500],
        )
        return {"success": False, "status_code": exc.code, "error": error_body[:500]}
    except Exception as exc:
        logger.error("reply_messages: unexpected error — %s", exc)
        return {"success": False, "status_code": 0, "error": str(exc)}


def send_broadcast(messages: list[str]) -> dict:
    """
    Convenience wrapper: push messages to the default LINE_USER_ID.
    Used by the daily scheduler job.
    """
    return push_messages(messages, user_id=_get_user_id())
