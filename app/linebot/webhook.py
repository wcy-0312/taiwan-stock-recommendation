"""
app/linebot/webhook.py — FastAPI router for the LINE Messaging API webhook.

LINE signature verification uses HMAC-SHA256 over the raw request body,
signed with LINE_CHANNEL_SECRET.  The signature is sent in the
`X-Line-Signature` header.

Reference: https://developers.line.biz/en/docs/messaging-api/receiving-messages/

Endpoints:
    GET  /health    — health check (used by Render)
    POST /webhook   — LINE webhook receiver
"""

from __future__ import annotations

import hashlib
import hmac
import base64
import json
import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Request, Response

from app.linebot.commands import dispatch_command
from app.linebot.notifier import reply_message_objects

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

@router.get("/health")
async def health_check() -> dict:
    """Render health check endpoint — always returns 200."""
    import os
    public_base_url = os.environ.get("PUBLIC_BASE_URL", "").rstrip("/")
    return {
        "status": "ok",
        "app": "台股智能雷達",
        "public_base_url_configured": bool(public_base_url),
    }


# ---------------------------------------------------------------------------
# Signature verification
# ---------------------------------------------------------------------------

def _verify_signature(body_bytes: bytes, signature: str) -> bool:
    """
    Verify the X-Line-Signature header.

    Parameters
    ----------
    body_bytes : bytes — raw request body
    signature  : str   — value of X-Line-Signature header (base64)

    Returns
    -------
    True if valid, False if invalid or LINE_CHANNEL_SECRET not configured.

    Note: LINE_CHANNEL_SECRET is read at call time (not at import time) so
    that environment variable changes after import are reflected.
    """
    import os
    channel_secret = os.environ.get("LINE_CHANNEL_SECRET", "")

    if not channel_secret:
        logger.warning("LINE_CHANNEL_SECRET not configured — skipping signature check")
        return True  # Allow in development (warn, don't block)

    try:
        secret_bytes = channel_secret.encode("utf-8")
        digest = hmac.new(secret_bytes, body_bytes, hashlib.sha256).digest()
        expected = base64.b64encode(digest).decode("utf-8")
        return hmac.compare_digest(expected, signature)
    except Exception as exc:
        logger.error("Signature verification error: %s", exc)
        return False


# ---------------------------------------------------------------------------
# Webhook receiver
# ---------------------------------------------------------------------------

@router.post("/webhook")
async def webhook(request: Request) -> Response:
    """
    Receive LINE webhook events.

    LINE sends a JSON body with an `events` list.  Each event has a `type`
    (e.g. "message", "follow", "unfollow") and a `source` with the user_id.

    We handle `message` events with `type == "text"` — all other events are
    acknowledged with 200 OK and ignored.
    """
    body_bytes = await request.body()
    signature = request.headers.get("X-Line-Signature", "")

    # Verify signature
    if not _verify_signature(body_bytes, signature):
        logger.warning("Invalid LINE signature from %s", request.client)
        raise HTTPException(status_code=400, detail="Invalid signature")

    # Parse body
    try:
        payload: dict[str, Any] = json.loads(body_bytes.decode("utf-8"))
    except Exception as exc:
        logger.error("Failed to parse webhook JSON: %s", exc)
        raise HTTPException(status_code=400, detail="Bad JSON")

    # Process events
    events: list[dict] = payload.get("events", [])
    logger.info("Received %d webhook events", len(events))

    for event in events:
        _handle_event(event)

    # LINE requires a 200 response with empty body
    return Response(content="OK", status_code=200)


def _handle_event(event: dict) -> None:
    """Dispatch a single LINE event."""
    event_type = event.get("type", "")

    if event_type != "message":
        logger.debug("Ignoring event type: %s", event_type)
        return

    message = event.get("message", {})
    if message.get("type") != "text":
        logger.debug("Ignoring non-text message type: %s", message.get("type"))
        return

    # Extract user and reply token
    source = event.get("source", {})
    user_id = source.get("userId", "")
    reply_token = event.get("replyToken", "")
    text = message.get("text", "").strip()

    if not user_id or not text:
        logger.debug("Skipping event with missing user_id or empty text")
        return

    logger.info("Message from %s: %s", user_id, text[:80])

    # Dispatch to command handler
    # dispatch_command returns list[dict] (LINE message objects)
    try:
        reply_objects = dispatch_command(user_id, text)
    except Exception as exc:
        logger.error("dispatch_command error for user=%s text=%r: %s", user_id, text, exc)
        reply_objects = [{"type": "text", "text": "抱歉，系統發生錯誤，請稍後再試。"}]

    # Reply using message objects
    if reply_token and reply_objects:
        result = reply_message_objects(reply_token, reply_objects)
        if not result.get("success"):
            logger.error(
                "Failed to reply to user=%s: status=%s error=%s",
                user_id,
                result.get("status_code"),
                result.get("error"),
            )
