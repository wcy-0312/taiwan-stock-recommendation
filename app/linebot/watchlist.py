"""
app/linebot/watchlist.py — SQLite-backed per-user watchlist CRUD.

Each user (LINE user_id) can maintain a list of ticker codes they want
to track.  The database is created automatically at WATCHLIST_DB_PATH
(configured in app/config.py, defaults to data/watchlist.db).

Table schema:
    watchlist(user_id TEXT, ticker TEXT, added_at TEXT)
    UNIQUE on (user_id, ticker) — duplicate adds are silently ignored.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import List

from app.config import WATCHLIST_DB_PATH


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

_DDL = """
CREATE TABLE IF NOT EXISTS watchlist (
    user_id   TEXT NOT NULL,
    ticker    TEXT NOT NULL,
    added_at  TEXT NOT NULL,
    PRIMARY KEY (user_id, ticker)
);
"""


def _connect() -> sqlite3.Connection:
    """Open (or create) the watchlist database."""
    db_path: Path = WATCHLIST_DB_PATH
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute(_DDL)
    conn.commit()
    return conn


# ---------------------------------------------------------------------------
# CRUD operations
# ---------------------------------------------------------------------------

def add_ticker(user_id: str, ticker: str) -> bool:
    """
    Add a ticker to a user's watchlist.

    Parameters
    ----------
    user_id : str — LINE user_id
    ticker  : str — stock code e.g. "2330" or "2330.TW" (stored as-is)

    Returns
    -------
    True  if the ticker was newly added.
    False if it was already present (idempotent, no error raised).
    """
    ticker = ticker.strip().upper()
    added_at = datetime.now(timezone.utc).isoformat()
    with _connect() as conn:
        try:
            conn.execute(
                "INSERT INTO watchlist (user_id, ticker, added_at) VALUES (?, ?, ?)",
                (user_id, ticker, added_at),
            )
            conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False  # already exists (PRIMARY KEY violation)


def remove_ticker(user_id: str, ticker: str) -> bool:
    """
    Remove a ticker from a user's watchlist.

    Parameters
    ----------
    user_id : str — LINE user_id
    ticker  : str — stock code

    Returns
    -------
    True  if the ticker was found and removed.
    False if the ticker was not in the watchlist.
    """
    ticker = ticker.strip().upper()
    with _connect() as conn:
        cursor = conn.execute(
            "DELETE FROM watchlist WHERE user_id = ? AND ticker = ?",
            (user_id, ticker),
        )
        conn.commit()
        return cursor.rowcount > 0


def get_watchlist(user_id: str) -> List[str]:
    """
    Return all tickers for a user, ordered by the time they were added (oldest first).

    Parameters
    ----------
    user_id : str — LINE user_id

    Returns
    -------
    List[str] — list of ticker strings (may be empty)
    """
    with _connect() as conn:
        rows = conn.execute(
            "SELECT ticker FROM watchlist WHERE user_id = ? ORDER BY added_at ASC",
            (user_id,),
        ).fetchall()
    return [row[0] for row in rows]


def clear_watchlist(user_id: str) -> int:
    """
    Remove all tickers for a user.

    Returns the number of rows deleted.
    """
    with _connect() as conn:
        cursor = conn.execute(
            "DELETE FROM watchlist WHERE user_id = ?",
            (user_id,),
        )
        conn.commit()
        return cursor.rowcount


def ticker_in_watchlist(user_id: str, ticker: str) -> bool:
    """Return True if the given ticker is already in the user's watchlist."""
    ticker = ticker.strip().upper()
    with _connect() as conn:
        row = conn.execute(
            "SELECT 1 FROM watchlist WHERE user_id = ? AND ticker = ? LIMIT 1",
            (user_id, ticker),
        ).fetchone()
    return row is not None
