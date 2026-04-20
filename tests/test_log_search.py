import csv
from pathlib import Path

import pytest

from ow_chat_logger.log_search import (
    SearchResult,
    SearchResultSet,
    history_for_player,
    search_logs,
)


def _write_csv(path: Path, rows: list[list[str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        csv.writer(fh).writerows(rows)


@pytest.fixture
def logs(tmp_path: Path) -> tuple[Path, Path]:
    chat = tmp_path / "chat_log.csv"
    hero = tmp_path / "hero_log.csv"
    _write_csv(
        chat,
        [
            ["2026-01-01 10:00:00", "Chiaki", "hello team", "team"],
            ["2026-01-01 10:00:05", "Chiaki123", "imposter line", "team"],
            ["2026-01-01 10:00:10", "NotChiaki", "also imposter", "all"],
            ["2026-01-01 10:01:00", "Bob", "GG WP", "all"],
            ["2026-01-01 10:02:00", "Bob", "nice ult CHIAKI", "team"],
            ["2026-01-01 10:03:00", "Ünicode", "grüße dich", "all"],
            ["2026-01-01 10:04:00", "chiaki", "lowercase variant", "team"],
            ["2026-01-01 10:05:00", "Alice", "good game", "all"],
            ["2026-01-01 10:06:00", "Alice", "team push mid", "team"],
            ["2026-01-01 10:07:00", "Eve", "go go", "team"],
            ["2026-01-01 10:08:00", "Mallory", "late message", "all"],
        ],
    )
    _write_csv(
        hero,
        [
            ["2026-01-01 09:59:00", "Chiaki", "Mercy"],
            ["2026-01-01 10:01:30", "Chiaki", "Kiriko"],
            ["2026-01-01 10:01:45", "Bob", "Reinhardt"],
            ["2026-01-01 10:02:30", "Alice", "Chiaki-skin-hero"],
            ["2026-01-01 10:09:00", "Mallory", "Lucio"],
        ],
    )
    return chat, hero


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
    rs = search_logs(
        "chiaki", chat_log_path=chat, hero_log_path=hero, channel_filter="team"
    )
    assert {r.source for r in rs.results} == {"team"}


def test_search_channel_filter_all(logs):
    chat, hero = logs
    rs = search_logs(
        "chiaki", chat_log_path=chat, hero_log_path=hero, channel_filter="all"
    )
    assert {r.source for r in rs.results} == {"all"}


def test_search_channel_filter_hero(logs):
    chat, hero = logs
    rs = search_logs(
        "chiaki", chat_log_path=chat, hero_log_path=hero, channel_filter="hero"
    )
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


def test_search_malformed_rows_skipped(tmp_path):
    chat = tmp_path / "chat_log.csv"
    hero = tmp_path / "hero_log.csv"
    with chat.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["2026-01-01 10:00:00", "Alice", "hello", "team"])
        w.writerow(["too", "few"])  # short row
        w.writerow(["2026-01-01 10:00:01", "Bob", "bye", "garbage-channel"])
        w.writerow(["2026-01-01 10:00:02", "Alice", "hi again", "all"])
    hero.write_text("", encoding="utf-8")

    rs = search_logs("a", chat_log_path=chat, hero_log_path=hero)
    # Alice's two rows survive; Bob with garbage-channel is skipped; short row skipped.
    assert len(rs.results) == 2
    assert {r.player for r in rs.results} == {"Alice"}


def test_search_missing_files_return_empty(tmp_path):
    chat = tmp_path / "nope_chat.csv"
    hero = tmp_path / "nope_hero.csv"
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
    assert (
        history_for_player("", chat_log_path=chat, hero_log_path=hero).results == []
    )
    assert (
        history_for_player("   ", chat_log_path=chat, hero_log_path=hero).results
        == []
    )


def test_history_limit_honored(logs):
    chat, hero = logs
    rs = history_for_player(
        "Chiaki", chat_log_path=chat, hero_log_path=hero, limit=2
    )
    assert len(rs.results) == 2
    assert rs.truncated is True


def test_history_missing_files_return_empty(tmp_path):
    rs = history_for_player(
        "Alice",
        chat_log_path=tmp_path / "missing_chat.csv",
        hero_log_path=tmp_path / "missing_hero.csv",
    )
    assert rs == SearchResultSet(results=[], truncated=False)


def test_search_match_field_player_only(logs):
    chat, hero = logs
    # "chiaki" appears as player (Chiaki, Chiaki123, NotChiaki, chiaki) AND
    # in message text ("nice ult CHIAKI") AND hero text ("Chiaki-skin-hero").
    # With match_field="player", rows matched solely by text/hero-text are excluded.
    rs = search_logs(
        "chiaki", chat_log_path=chat, hero_log_path=hero, match_field="player"
    )
    players = {r.player for r in rs.results}
    # Bob had "nice ult CHIAKI" — text-only match, must be excluded.
    assert "Bob" not in players
    # Alice had hero text "Chiaki-skin-hero" — text-only match, must be excluded.
    assert "Alice" not in players
    # Direct player-name matches stay.
    assert {"Chiaki", "Chiaki123", "NotChiaki", "chiaki"}.issubset(players)


def test_search_match_field_text_only(logs):
    chat, hero = logs
    rs = search_logs(
        "chiaki", chat_log_path=chat, hero_log_path=hero, match_field="text"
    )
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
