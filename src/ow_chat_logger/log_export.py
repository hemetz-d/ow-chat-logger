"""Export the persisted chat-log SQLite store to ``.csv`` / ``.txt``.

Moving the canonical store from append-only CSV to SQLite (T-43) closed
the "open the file in any text tool" affordance users used to have. This
module restores it: callers point at the DB and get back a portable file
they can paste into a bug report, share with a teammate, or archive.

Both entry points open the DB **read-only** (``mode=ro``) so an export
running in parallel with a live capture cannot accidentally mutate the
canonical store. Both stream rows from a single ``SELECT`` — there is no
intermediate materialization, so memory cost is bounded regardless of how
large the user's history has grown.

The TXT format mirrors the colorized console writer in
:mod:`ow_chat_logger.logger` (minus the ANSI escapes). Keeping the two in
sync means a user who is already used to reading their console output
will recognize the export at a glance.
"""

from __future__ import annotations

import csv
import sqlite3
from pathlib import Path
from typing import Literal

ChannelFilter = Literal["team", "all", "hero"]

_VALID_CHANNELS = frozenset({"team", "all", "hero"})

# Header row for the CSV export. Order matches the `messages` table layout
# the user would see if they cracked the SQLite file open directly.
_CSV_HEADER = ("timestamp", "player", "text", "source")


def _open_readonly(db_path: Path) -> sqlite3.Connection:
    """Open ``db_path`` read-only via the SQLite URI form.

    Read-only mode keeps the export path strictly non-destructive even when
    the live writer is appending new rows in parallel.
    """
    if not db_path.exists():
        raise FileNotFoundError(
            f"No chat history found at {db_path}. Start a capture session first."
        )
    uri = f"file:{db_path.as_posix()}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def _build_query(
    channel_filter: ChannelFilter | None,
    since: str | None,
    until: str | None,
) -> tuple[str, dict[str, object]]:
    """Compose the chronological SELECT and its bound parameters.

    Timestamps are stored as ISO-shaped TEXT (``YYYY-MM-DD HH:MM:SS``) which
    sorts lexicographically, so ``>=`` / ``<=`` against caller-supplied
    strings is correct without any conversion.
    """
    if channel_filter is not None and channel_filter not in _VALID_CHANNELS:
        raise ValueError(f"channel_filter must be one of {sorted(_VALID_CHANNELS)}")

    sql = """
        SELECT timestamp, player, text, source FROM messages
        WHERE (:channel IS NULL OR source = :channel)
          AND (:since   IS NULL OR timestamp >= :since)
          AND (:until   IS NULL OR timestamp <= :until)
        ORDER BY timestamp ASC, id ASC
    """
    params: dict[str, object] = {
        "channel": channel_filter,
        "since": since,
        "until": until,
    }
    return sql, params


def export_to_csv(
    out_path: Path | str,
    *,
    db_path: Path | str | None = None,
    channel_filter: ChannelFilter | None = None,
    since: str | None = None,
    until: str | None = None,
) -> int:
    """Stream chat history to a UTF-8 CSV file.

    Returns the number of data rows written (header excluded). The output
    is a faithful tabular dump: one row per message in chronological order,
    with the same column set the SQLite store carries.
    """
    out_path = Path(out_path)
    db_path = _resolve_db_path(db_path)

    sql, params = _build_query(channel_filter, since, until)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    written = 0
    conn = _open_readonly(db_path)
    try:
        # ``newline=""`` matches the standard csv-module recommendation on
        # Windows so we don't end up with extra blank lines on \r\n hosts.
        with out_path.open("w", encoding="utf-8", newline="") as fh:
            writer = csv.writer(fh)
            writer.writerow(_CSV_HEADER)
            for row in conn.execute(sql, params):
                writer.writerow(
                    (row["timestamp"], row["player"], row["text"], row["source"])
                )
                written += 1
    finally:
        conn.close()
    return written


def export_to_txt(
    out_path: Path | str,
    *,
    db_path: Path | str | None = None,
    channel_filter: ChannelFilter | None = None,
    since: str | None = None,
    until: str | None = None,
    include_hero: bool = True,
) -> int:
    """Stream chat history to a plain-text file.

    Format matches :mod:`ow_chat_logger.logger`'s console writer minus the
    ANSI escapes: ``<timestamp> | TEAM | Alice: hi`` for chat rows,
    ``<timestamp> | HERO | Alice / Mercy`` for hero rows.

    ``include_hero=False`` filters out hero rows even when they would
    otherwise survive ``channel_filter`` — useful for "give me a chat-only
    transcript" without requiring the caller to compose two separate
    filters.
    """
    out_path = Path(out_path)
    db_path = _resolve_db_path(db_path)

    sql, params = _build_query(channel_filter, since, until)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    written = 0
    conn = _open_readonly(db_path)
    try:
        with out_path.open("w", encoding="utf-8", newline="") as fh:
            for row in conn.execute(sql, params):
                source = row["source"]
                if source == "hero" and not include_hero:
                    continue
                fh.write(_format_txt_row(row["timestamp"], row["player"], row["text"], source))
                fh.write("\n")
                written += 1
    finally:
        conn.close()
    return written


def _format_txt_row(timestamp: str, player: str, text: str, source: str) -> str:
    tag = source.upper()
    if source == "hero":
        return f"{timestamp} | {tag:<4} | {player} / {text}"
    return f"{timestamp} | {tag:<4} | {player}: {text}"


def _resolve_db_path(db_path: Path | str | None) -> Path:
    """Default to the canonical ``chat_db`` path when caller leaves it None.

    Tests and explicit callers can pass any path; the GUI will rely on the
    default. Resolving lazily keeps unit tests free of environment setup
    and the GUI free of an extra plumbing layer.
    """
    if db_path is not None:
        return Path(db_path)
    from ow_chat_logger.config import get_app_paths

    return get_app_paths().chat_db
