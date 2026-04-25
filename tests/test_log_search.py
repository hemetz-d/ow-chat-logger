"""Tests for the SQLite-backed search layer.

The behavior contract that lives in this file is the same one we had under
the old CSV layout — channel filters, match fields, case insensitivity,
exact-match history, limit + truncation, newest-first ordering, missing-file
empty result. Only the fixture mechanism changes: instead of writing CSVs
and pointing log_search at them, we seed the SQLite ``messages`` table
directly via ``_seed_db``.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from ow_chat_logger._chat_db import open_db
from ow_chat_logger.log_search import (
    SearchResult,
    SearchResultSet,
    clear_log_search_cache,
    history_for_player,
    search_logs,
)


def _seed_db(
    db_path: Path,
    *,
    chat_rows: list[tuple[str, str, str, str]],
    hero_rows: list[tuple[str, str, str]],
) -> None:
    """Insert chat + hero rows directly into the SQLite store.

    ``chat_rows`` are ``(timestamp, player, text, chat_type)`` tuples;
    ``hero_rows`` are ``(timestamp, player, hero_name)``. Rows with an
    invalid ``chat_type`` (anything outside {team, all, hero}) are skipped
    silently — this keeps the same "tolerant of bad data" surface that the
    old ``_write_csv``-based fixture had, without making the production
    writer permissive.
    """
    conn = open_db(db_path)
    try:
        for ts, player, text, chat_type in chat_rows:
            source = chat_type.strip().lower()
            if source not in ("team", "all"):
                continue
            conn.execute(
                "INSERT INTO messages "
                "(timestamp, player, player_lc, text, text_lc, source) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (ts, player, player.lower(), text, text.lower(), source),
            )
        for ts, player, hero_name in hero_rows:
            conn.execute(
                "INSERT INTO messages "
                "(timestamp, player, player_lc, text, text_lc, source) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (ts, player, player.lower(), hero_name, hero_name.lower(), "hero"),
            )
        conn.commit()
    finally:
        conn.close()


@pytest.fixture(autouse=True)
def _isolated_log_search_cache():
    """Drop any cached connections between tests so paths don't collide."""
    clear_log_search_cache()
    yield
    clear_log_search_cache()


@pytest.fixture
def logs(tmp_path: Path) -> tuple[Path, Path]:
    """Seed a single DB and return ``(db, db)`` for compatibility with the
    existing ``chat_log_path`` / ``hero_log_path`` argument pair."""
    db = tmp_path / "chat_log.sqlite"
    _seed_db(
        db,
        chat_rows=[
            ("2026-01-01 10:00:00", "Chiaki", "hello team", "team"),
            ("2026-01-01 10:00:05", "Chiaki123", "imposter line", "team"),
            ("2026-01-01 10:00:10", "NotChiaki", "also imposter", "all"),
            ("2026-01-01 10:01:00", "Bob", "GG WP", "all"),
            ("2026-01-01 10:02:00", "Bob", "nice ult CHIAKI", "team"),
            ("2026-01-01 10:03:00", "Ünicode", "grüße dich", "all"),
            ("2026-01-01 10:04:00", "chiaki", "lowercase variant", "team"),
            ("2026-01-01 10:05:00", "Alice", "good game", "all"),
            ("2026-01-01 10:06:00", "Alice", "team push mid", "team"),
            ("2026-01-01 10:07:00", "Eve", "go go", "team"),
            ("2026-01-01 10:08:00", "Mallory", "late message", "all"),
        ],
        hero_rows=[
            ("2026-01-01 09:59:00", "Chiaki", "Mercy"),
            ("2026-01-01 10:01:30", "Chiaki", "Kiriko"),
            ("2026-01-01 10:01:45", "Bob", "Reinhardt"),
            ("2026-01-01 10:02:30", "Alice", "Chiaki-skin-hero"),
            ("2026-01-01 10:09:00", "Mallory", "Lucio"),
        ],
    )
    return db, db


def _ts(rs: SearchResultSet) -> list[str]:
    return [r.timestamp for r in rs.results]


def test_search_substring_player(logs):
    chat, hero = logs
    rs = search_logs("bob", chat_log_path=chat, hero_log_path=hero)
    players = {r.player for r in rs.results}
    assert players == {"Bob"}
    assert all(not r.truncated for r in [rs])


def test_search_substring_text(logs):
    chat, hero = logs
    rs = search_logs("imposter", chat_log_path=chat, hero_log_path=hero)
    assert {r.text for r in rs.results} == {"imposter line", "also imposter"}


def test_search_matches_both_player_and_text_simultaneously(logs):
    chat, hero = logs
    # "chiaki" hits player (Chiaki, Chiaki123, NotChiaki, chiaki) AND
    # message text ("nice ult CHIAKI") AND hero text ("Chiaki-skin-hero") AND
    # hero player (Chiaki x2).
    rs = search_logs("chiaki", chat_log_path=chat, hero_log_path=hero)
    sources = {r.source for r in rs.results}
    assert sources == {"team", "all", "hero"}
    assert len(rs.results) == 8


def test_search_case_insensitive(logs):
    chat, hero = logs
    rs_lower = search_logs("chiaki", chat_log_path=chat, hero_log_path=hero)
    rs_upper = search_logs("CHIAKI", chat_log_path=chat, hero_log_path=hero)
    rs_mixed = search_logs("ChIaKi", chat_log_path=chat, hero_log_path=hero)
    assert _ts(rs_lower) == _ts(rs_upper) == _ts(rs_mixed)


def test_search_channel_filter_team(logs):
    chat, hero = logs
    rs = search_logs("chiaki", chat_log_path=chat, hero_log_path=hero, channel_filter="team")
    assert {r.source for r in rs.results} == {"team"}


def test_search_channel_filter_all(logs):
    chat, hero = logs
    rs = search_logs("chiaki", chat_log_path=chat, hero_log_path=hero, channel_filter="all")
    assert {r.source for r in rs.results} == {"all"}


def test_search_channel_filter_hero(logs):
    chat, hero = logs
    rs = search_logs("chiaki", chat_log_path=chat, hero_log_path=hero, channel_filter="hero")
    assert {r.source for r in rs.results} == {"hero"}
    # Both Chiaki hero rows + Alice's Chiaki-skin-hero.
    assert len(rs.results) == 3


def test_search_newest_first_across_files(logs):
    chat, hero = logs
    rs = search_logs("chiaki", chat_log_path=chat, hero_log_path=hero)
    timestamps = _ts(rs)
    assert timestamps == sorted(timestamps, reverse=True)


def test_search_limit_truncates_and_sets_flag(logs):
    chat, hero = logs
    rs = search_logs("chiaki", chat_log_path=chat, hero_log_path=hero, limit=3)
    assert len(rs.results) == 3
    assert rs.truncated is True
    # Truncation keeps the newest matches.
    assert rs.results[0].timestamp >= rs.results[-1].timestamp


def test_search_missing_files_return_empty(tmp_path):
    chat = tmp_path / "nope_chat.sqlite"
    hero = tmp_path / "nope_hero.sqlite"
    rs = search_logs("anything", chat_log_path=chat, hero_log_path=hero)
    assert rs == SearchResultSet(results=[], truncated=False)


def test_search_empty_query_returns_empty(logs):
    chat, hero = logs
    assert search_logs("", chat_log_path=chat, hero_log_path=hero).results == []
    assert search_logs("   ", chat_log_path=chat, hero_log_path=hero).results == []


def test_history_exact_match_case_insensitive(logs):
    chat, hero = logs
    rs_lower = history_for_player("chiaki", chat_log_path=chat, hero_log_path=hero)
    rs_upper = history_for_player("CHIAKI", chat_log_path=chat, hero_log_path=hero)
    assert _ts(rs_lower) == _ts(rs_upper)


def test_history_rejects_substring_neighbors(logs):
    chat, hero = logs
    rs = history_for_player("Chiaki", chat_log_path=chat, hero_log_path=hero)
    players = {r.player for r in rs.results}
    # "Chiaki123" and "NotChiaki" must be excluded; "chiaki" (case variant) included.
    assert "Chiaki123" not in players
    assert "NotChiaki" not in players
    assert "Chiaki" in players
    assert "chiaki" in players


def test_history_pulls_chat_and_hero_newest_first(logs):
    chat, hero = logs
    rs = history_for_player("Chiaki", chat_log_path=chat, hero_log_path=hero)
    sources = {r.source for r in rs.results}
    assert sources == {"team", "hero"}  # Chiaki has no "all" rows in the fixture
    timestamps = [r.timestamp for r in rs.results]
    assert timestamps == sorted(timestamps, reverse=True)


def test_history_empty_player_returns_empty(logs):
    chat, hero = logs
    assert history_for_player("", chat_log_path=chat, hero_log_path=hero).results == []
    assert history_for_player("   ", chat_log_path=chat, hero_log_path=hero).results == []


def test_history_limit_honored(logs):
    chat, hero = logs
    rs = history_for_player("Chiaki", chat_log_path=chat, hero_log_path=hero, limit=2)
    assert len(rs.results) == 2
    assert rs.truncated is True


def test_history_missing_files_return_empty(tmp_path):
    rs = history_for_player(
        "Alice",
        chat_log_path=tmp_path / "missing_chat.sqlite",
        hero_log_path=tmp_path / "missing_hero.sqlite",
    )
    assert rs == SearchResultSet(results=[], truncated=False)


def test_search_match_field_player_only(logs):
    chat, hero = logs
    # "chiaki" appears as player (Chiaki, Chiaki123, NotChiaki, chiaki) AND
    # in message text ("nice ult CHIAKI") AND hero text ("Chiaki-skin-hero").
    # With match_field="player", rows matched solely by text/hero-text are excluded.
    rs = search_logs("chiaki", chat_log_path=chat, hero_log_path=hero, match_field="player")
    players = {r.player for r in rs.results}
    # Bob had "nice ult CHIAKI" — text-only match, must be excluded.
    assert "Bob" not in players
    # Alice had hero text "Chiaki-skin-hero" — text-only match, must be excluded.
    assert "Alice" not in players
    # Direct player-name matches stay.
    assert {"Chiaki", "Chiaki123", "NotChiaki", "chiaki"}.issubset(players)


def test_search_match_field_text_only(logs):
    chat, hero = logs
    rs = search_logs("chiaki", chat_log_path=chat, hero_log_path=hero, match_field="text")
    players = {r.player for r in rs.results}
    # Player-only matches (the four Chiaki-named rows that don't mention
    # "chiaki" in text) must be excluded. Only Bob's "nice ult CHIAKI"
    # message and Alice's "Chiaki-skin-hero" hero row should survive.
    assert players == {"Bob", "Alice"}


def test_search_match_field_player_with_channel_filter(logs):
    chat, hero = logs
    # Scope player-name search to the hero channel only.
    rs = search_logs(
        "chiaki",
        chat_log_path=chat,
        hero_log_path=hero,
        match_field="player",
        channel_filter="hero",
    )
    assert {r.source for r in rs.results} == {"hero"}
    # Two Chiaki hero rows; Alice's "Chiaki-skin-hero" must NOT match
    # because Alice is not the player.
    assert {r.player for r in rs.results} == {"Chiaki"}
    assert len(rs.results) == 2


def test_result_row_fields_populated(logs):
    chat, hero = logs
    rs = history_for_player("Bob", chat_log_path=chat, hero_log_path=hero)
    by_source = {r.source: r for r in rs.results}
    chat_row = by_source["all"] if "all" in by_source else by_source["team"]
    assert isinstance(chat_row, SearchResult)
    assert chat_row.player == "Bob"
    assert chat_row.timestamp.startswith("2026-01-01")
    hero_row = by_source["hero"]
    assert hero_row.text == "Reinhardt"


# ── New SQLite-specific tests ───────────────────────────────────────────────


def test_search_like_metacharacters_treated_literally(tmp_path):
    """A user query containing ``%`` must NOT be expanded as a wildcard."""
    db = tmp_path / "chat.sqlite"
    _seed_db(
        db,
        chat_rows=[
            ("2026-01-01 10:00:00", "100%er", "first", "team"),
            ("2026-01-01 10:01:00", "abc", "second", "team"),
            ("2026-01-01 10:02:00", "xyz", "third", "team"),
        ],
        hero_rows=[],
    )
    rs = search_logs("100%", chat_log_path=db, hero_log_path=db)
    # Without escape: ``LIKE '%100%%'`` would match every row that starts
    # with "100" (and via accident, every row at all if the engine doesn't
    # interpret the trailing %). With the escape, only "100%er" matches.
    assert {r.player for r in rs.results} == {"100%er"}


def test_search_underscore_treated_literally(tmp_path):
    """LIKE ``_`` is the single-char wildcard; user input must be escaped."""
    db = tmp_path / "chat.sqlite"
    _seed_db(
        db,
        chat_rows=[
            ("2026-01-01 10:00:00", "a_b", "ok", "team"),
            ("2026-01-01 10:01:00", "axb", "no", "team"),  # would match unescaped _
            ("2026-01-01 10:02:00", "zzz", "no", "team"),
        ],
        hero_rows=[],
    )
    rs = search_logs("a_b", chat_log_path=db, hero_log_path=db)
    assert {r.player for r in rs.results} == {"a_b"}


def test_writer_and_reader_use_same_db(tmp_path):
    """End-to-end round-trip: ``MessageLogger.log`` then ``search_logs``."""
    from ow_chat_logger.logger import MessageLogger

    db = tmp_path / "chat.sqlite"
    chat_logger = MessageLogger(str(db))
    hero_logger = MessageLogger(str(db), print_mode="hero", include_chat_type=False)

    chat_logger.log("2026-01-01 10:00:00", "pixelwolf", "grouping mid", "team")
    chat_logger.log("2026-01-01 10:00:05", "rayner", "on it", "team")
    hero_logger.log("2026-01-01 10:00:10", "pixelwolf", "Ana")
    chat_logger.close()
    hero_logger.close()

    rs = search_logs("pixelwolf", chat_log_path=db, hero_log_path=db)
    sources = {r.source for r in rs.results}
    assert sources == {"team", "hero"}
    assert {r.player for r in rs.results} == {"pixelwolf"}


def test_clear_log_search_cache_releases_connections(tmp_path):
    """After clearing the cache the next query opens a fresh connection."""
    db = tmp_path / "chat.sqlite"
    _seed_db(
        db,
        chat_rows=[("2026-01-01 10:00:00", "alice", "hi", "team")],
        hero_rows=[],
    )
    rs1 = search_logs("alice", chat_log_path=db, hero_log_path=db)
    assert len(rs1.results) == 1

    clear_log_search_cache()
    # The DB file still exists; the cache was just dropped. A fresh query
    # must reopen and return the same data.
    rs2 = search_logs("alice", chat_log_path=db, hero_log_path=db)
    assert len(rs2.results) == 1


def test_search_invalid_match_field_raises(tmp_path):
    db = tmp_path / "chat.sqlite"
    _seed_db(db, chat_rows=[], hero_rows=[])
    with pytest.raises(ValueError):
        search_logs("anything", chat_log_path=db, hero_log_path=db, match_field="bogus")  # type: ignore[arg-type]


def test_search_invalid_channel_filter_raises(tmp_path):
    db = tmp_path / "chat.sqlite"
    _seed_db(db, chat_rows=[], hero_rows=[])
    with pytest.raises(ValueError):
        search_logs("anything", chat_log_path=db, hero_log_path=db, channel_filter="bogus")  # type: ignore[arg-type]


def test_db_check_constraint_rejects_bad_source(tmp_path):
    """Direct INSERT with a bad source is rejected by the schema CHECK."""
    db = tmp_path / "chat.sqlite"
    conn = open_db(db)
    try:
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO messages "
                "(timestamp, player, player_lc, text, text_lc, source) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                ("2026-01-01 10:00:00", "alice", "alice", "hi", "hi", "garbage"),
            )
    finally:
        conn.close()
