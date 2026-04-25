"""Internal helpers for the chat-log SQLite store.

Shared schema + thin connection helpers used by both the writer
(:mod:`ow_chat_logger.logger`) and the reader
(:mod:`ow_chat_logger.log_search`). Keeping this in a tiny private module
avoids a circular import between the two and gives both sides one place to
look up the schema definition.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

# Schema is idempotent — both the writer and the reader call ``open_db``
# unconditionally at startup; ``CREATE … IF NOT EXISTS`` makes that safe.
SCHEMA = """
CREATE TABLE IF NOT EXISTS messages (
    id          INTEGER PRIMARY KEY,
    timestamp   TEXT NOT NULL,
    player      TEXT NOT NULL,
    player_lc   TEXT NOT NULL,
    text        TEXT NOT NULL,
    text_lc     TEXT NOT NULL,
    source      TEXT NOT NULL CHECK (source IN ('team','all','hero'))
);
CREATE INDEX IF NOT EXISTS idx_player_lc ON messages (player_lc);
CREATE INDEX IF NOT EXISTS idx_source    ON messages (source);
CREATE INDEX IF NOT EXISTS idx_timestamp ON messages (timestamp DESC);
"""

# WAL gives us concurrent reads alongside writes; ``synchronous=NORMAL`` is
# safe with WAL and noticeably faster than the FULL default for our load.
_PRAGMAS = """
PRAGMA journal_mode = WAL;
PRAGMA synchronous  = NORMAL;
"""


def open_db(path: Path) -> sqlite3.Connection:
    """Open (or create) the chat-log DB at ``path`` for read+write use.

    Ensures the parent directory exists, applies the schema, sets pragmas,
    and returns a thread-safe connection (``check_same_thread=False``) with
    ``sqlite3.Row`` factories for dict-style access.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    conn.executescript(_PRAGMAS)
    return conn
