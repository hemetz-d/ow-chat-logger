"""Search over the persisted chat-log SQLite store.

The previous implementation re-scanned both CSV log files on every call.
That layer is gone — chat and hero rows now live in a single SQLite
``messages`` table written directly by :class:`MessageLogger`. This module
queries it via parameterized SQL with an indexed lower-case mirror column
(``player_lc``) for case-insensitive matches.

The public surface (``search_logs``, ``history_for_player``, the
``SearchResult`` / ``SearchResultSet`` dataclasses, ``clear_log_search_cache``)
is unchanged; the GUI consumes results identically.
"""

from __future__ import annotations

import logging
import sqlite3
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from ow_chat_logger._chat_db import open_db

logger = logging.getLogger(__name__)

Source = Literal["team", "all", "hero"]
ChannelFilter = Literal["team", "all", "hero"]
MatchField = Literal["player", "text", "both"]

_DEFAULT_SEARCH_LIMIT = 500
_DEFAULT_HISTORY_LIMIT = 1000

_VALID_CHANNELS = frozenset({"team", "all", "hero"})
_VALID_MATCH_FIELDS = frozenset({"player", "text", "both"})


@dataclass(frozen=True)
class SearchResult:
    timestamp: str
    player: str
    text: str
    source: Source


@dataclass(frozen=True)
class SearchResultSet:
    results: list[SearchResult]
    truncated: bool


# ── Connection cache ─────────────────────────────────────────────────────────
# A single connection per resolved DB path, lazily opened. Keyed by path so
# tests that swap ``OW_CHAT_LOG_DIR`` (and therefore the DB location) get a
# fresh connection instead of querying the previous test's database.

_conn_cache: dict[Path, sqlite3.Connection] = {}
_conn_lock = threading.Lock()


def _get_conn(path: Path) -> sqlite3.Connection:
    """Return a cached connection for ``path``, opening it on first use."""
    resolved = Path(path)
    with _conn_lock:
        conn = _conn_cache.get(resolved)
        if conn is None:
            conn = open_db(resolved)
            _conn_cache[resolved] = conn
        return conn


def clear_log_search_cache() -> None:
    """Close any cached SQLite connections.

    Public hook used by tests to release file handles between fixtures.
    The DB file itself is the canonical store and is NOT deleted here —
    callers that want a clean slate should ``unlink`` it themselves before
    the next query reopens it.
    """
    with _conn_lock:
        for conn in _conn_cache.values():
            try:
                conn.close()
            except Exception:
                pass
        _conn_cache.clear()


# ── LIKE-pattern escape ──────────────────────────────────────────────────────
# Parameterized binding handles SQL injection. ``LIKE`` has its own
# metacharacters (``%`` ``_`` ``\``) that we escape so a literal user query
# for "100%" doesn't turn into a wildcard match.


def _escape_like(s: str) -> str:
    return s.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


# ── Public queries ───────────────────────────────────────────────────────────


def search_logs(
    query: str,
    *,
    chat_log_path: Path,
    hero_log_path: Path | None = None,
    channel_filter: ChannelFilter | None = None,
    match_field: MatchField = "both",
    limit: int = _DEFAULT_SEARCH_LIMIT,
) -> SearchResultSet:
    """Case-insensitive substring search over the canonical SQLite store.

    ``match_field`` selects which column(s) the query must hit:
      * ``"player"`` — player column only
      * ``"text"``   — message/hero-text column only
      * ``"both"``   — either column (default, back-compat)

    ``chat_log_path`` is the DB path. ``hero_log_path`` is accepted for
    backward compatibility with the old two-CSV signature but ignored —
    chat and hero rows live in the same DB now.
    """
    needle = query.strip().lower()
    if not needle:
        return SearchResultSet(results=[], truncated=False)

    if match_field not in _VALID_MATCH_FIELDS:
        raise ValueError(f"match_field must be one of {sorted(_VALID_MATCH_FIELDS)}")
    if channel_filter is not None and channel_filter not in _VALID_CHANNELS:
        raise ValueError(f"channel_filter must be one of {sorted(_VALID_CHANNELS)}")

    chat_log_path = Path(chat_log_path)
    if not chat_log_path.exists():
        return SearchResultSet(results=[], truncated=False)

    match_player = match_field in ("player", "both")
    match_text = match_field in ("text", "both")
    pattern = f"%{_escape_like(needle)}%"

    sql = """
        SELECT timestamp, player, text, source FROM messages
        WHERE (
            (:match_player = 1 AND player_lc LIKE :pattern ESCAPE '\\')
         OR (:match_text   = 1 AND text_lc   LIKE :pattern ESCAPE '\\')
        )
          AND (:channel IS NULL OR source = :channel)
        ORDER BY timestamp DESC
        LIMIT :over_limit
    """
    params = {
        "match_player": 1 if match_player else 0,
        "match_text": 1 if match_text else 0,
        "pattern": pattern,
        "channel": channel_filter,
        "over_limit": limit + 1,
    }

    return _run_query(chat_log_path, sql, params, limit)


def history_for_player(
    player: str,
    *,
    chat_log_path: Path,
    hero_log_path: Path | None = None,
    limit: int = _DEFAULT_HISTORY_LIMIT,
) -> SearchResultSet:
    """Exact (case-insensitive) match on the player column.

    Substring neighbors are explicitly rejected — ``"Chiaki"`` does not match
    ``"Chiaki123"`` or ``"NotChiaki"``. Empty/whitespace-only player returns
    an empty result set rather than every row.

    ``hero_log_path`` is accepted for backward compatibility but ignored —
    one DB now holds both chat and hero rows.
    """
    target = player.strip().lower()
    if not target:
        return SearchResultSet(results=[], truncated=False)

    chat_log_path = Path(chat_log_path)
    if not chat_log_path.exists():
        return SearchResultSet(results=[], truncated=False)

    sql = """
        SELECT timestamp, player, text, source FROM messages
        WHERE player_lc = :player_lc
        ORDER BY timestamp DESC
        LIMIT :over_limit
    """
    params = {"player_lc": target, "over_limit": limit + 1}
    return _run_query(chat_log_path, sql, params, limit)


def _run_query(
    db_path: Path,
    sql: str,
    params: dict,
    limit: int,
) -> SearchResultSet:
    """Execute ``sql`` with ``params``, materialize ``SearchResult`` rows.

    The query is asked for ``limit + 1`` rows so the caller can tell whether
    truncation occurred. We trim to ``limit`` here and set the flag.
    """
    try:
        conn = _get_conn(db_path)
        with _conn_lock:
            rows = list(conn.execute(sql, params))
    except sqlite3.Error as exc:
        logger.debug("log_search query failed against %s: %s", db_path, exc)
        return SearchResultSet(results=[], truncated=False)

    truncated = len(rows) > limit
    if truncated:
        rows = rows[:limit]
    results = [
        SearchResult(
            timestamp=r["timestamp"],
            player=r["player"],
            text=r["text"],
            source=r["source"],  # type: ignore[arg-type]
        )
        for r in rows
    ]
    return SearchResultSet(results=results, truncated=truncated)
