"""Search over persisted chat and hero CSV logs.

Pure search over the append-only CSVs written by :class:`MessageLogger`. No
GUI dependencies; the GUI layer consumes :class:`SearchResultSet` via the two
entry points :func:`search_logs` and :func:`history_for_player`.
"""

from __future__ import annotations

import csv
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Literal

logger = logging.getLogger(__name__)

Source = Literal["team", "all", "hero"]
ChannelFilter = Literal["team", "all", "hero"]
MatchField = Literal["player", "text", "both"]

_DEFAULT_SEARCH_LIMIT = 500
_DEFAULT_HISTORY_LIMIT = 1000


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


def search_logs(
    query: str,
    *,
    chat_log_path: Path,
    hero_log_path: Path,
    channel_filter: ChannelFilter | None = None,
    match_field: MatchField = "both",
    limit: int = _DEFAULT_SEARCH_LIMIT,
) -> SearchResultSet:
    """Case-insensitive substring search.

    ``match_field`` selects which column(s) the query must hit:
      * ``"player"`` — player column only
      * ``"text"``   — message/hero-text column only
      * ``"both"``   — either column (default, back-compat)

    Empty/whitespace-only queries return an empty result set.
    """
    needle = query.strip().lower()
    if not needle:
        return SearchResultSet(results=[], truncated=False)

    match_player = match_field in ("player", "both")
    match_text = match_field in ("text", "both")

    def _match(r: SearchResult) -> bool:
        if match_player and needle in r.player.lower():
            return True
        if match_text and needle in r.text.lower():
            return True
        return False

    hits: list[SearchResult] = []
    if channel_filter in (None, "team", "all"):
        hits.extend(
            r
            for r in _read_chat_rows(chat_log_path)
            if _match(r) and (channel_filter is None or r.source == channel_filter)
        )
    if channel_filter in (None, "hero"):
        hits.extend(r for r in _read_hero_rows(hero_log_path) if _match(r))

    return _finalize(hits, limit)


def history_for_player(
    player: str,
    *,
    chat_log_path: Path,
    hero_log_path: Path,
    limit: int = _DEFAULT_HISTORY_LIMIT,
) -> SearchResultSet:
    """Exact (case-insensitive) match on the player column across both logs.

    Substring neighbors are explicitly rejected — ``"Chiaki"`` does not match
    ``"Chiaki123"`` or ``"NotChiaki"``. Empty/whitespace-only player returns
    an empty result set rather than every row.
    """
    target = player.strip().lower()
    if not target:
        return SearchResultSet(results=[], truncated=False)

    hits: list[SearchResult] = [
        r for r in _read_chat_rows(chat_log_path) if r.player.lower() == target
    ]
    hits.extend(r for r in _read_hero_rows(hero_log_path) if r.player.lower() == target)

    return _finalize(hits, limit)


def _finalize(hits: list[SearchResult], limit: int) -> SearchResultSet:
    hits.sort(key=lambda r: r.timestamp, reverse=True)
    truncated = len(hits) > limit
    if truncated:
        hits = hits[:limit]
    return SearchResultSet(results=hits, truncated=truncated)


def _read_chat_rows(path: Path) -> Iterable[SearchResult]:
    for row in _iter_csv(path, expected_cols=4):
        timestamp, player, text, chat_type = row[0], row[1], row[2], row[3]
        source = chat_type.strip().lower()
        if source not in ("team", "all"):
            continue
        yield SearchResult(
            timestamp=timestamp,
            player=player,
            text=text,
            source=source,  # type: ignore[arg-type]
        )


def _read_hero_rows(path: Path) -> Iterable[SearchResult]:
    for row in _iter_csv(path, expected_cols=3):
        yield SearchResult(
            timestamp=row[0],
            player=row[1],
            text=row[2],
            source="hero",
        )


def _iter_csv(path: Path, *, expected_cols: int) -> Iterable[list[str]]:
    if not path.exists():
        return
    skipped = 0
    try:
        with path.open("r", newline="", encoding="utf-8") as fh:
            reader = csv.reader(fh)
            while True:
                try:
                    row = next(reader)
                except StopIteration:
                    break
                except csv.Error:
                    skipped += 1
                    continue
                if len(row) < expected_cols:
                    skipped += 1
                    continue
                yield row
    except OSError as exc:
        logger.debug("log_search: could not read %s: %s", path, exc)
        return
    if skipped:
        logger.debug("log_search: skipped %d malformed rows in %s", skipped, path)
