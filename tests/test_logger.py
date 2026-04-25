"""Tests for :class:`MessageLogger` over the SQLite store.

The schema is shared with :mod:`ow_chat_logger.log_search`; tests here
verify the writer's contract: rows land in the ``messages`` table with the
right ``source`` (``team`` / ``all`` for chat, always ``hero`` for the
hero logger), ``chat_type`` validation still raises, the closed-after-use
invariant still raises, and the colorized-print path is unchanged.
"""

import sqlite3
from pathlib import Path

import pytest

from ow_chat_logger.logger import MessageLogger


def _read_messages(db_path: Path) -> list[tuple[str, str, str, str]]:
    """Return ``(timestamp, player, text, source)`` rows in insertion order."""
    conn = sqlite3.connect(db_path)
    try:
        rows = list(
            conn.execute("SELECT timestamp, player, text, source FROM messages ORDER BY id")
        )
    finally:
        conn.close()
    return rows


def test_logger_writes_multiple_rows_and_flushes(tmp_path: Path):
    db_path = tmp_path / "chat.sqlite"
    logger = MessageLogger(str(db_path))

    logger.log("2026-01-01 00:00:00", "Alice", "hello", "team")
    logger.log("2026-01-01 00:00:01", "Bob", "bye", "all")
    logger.flush()
    logger.close()

    assert _read_messages(db_path) == [
        ("2026-01-01 00:00:00", "Alice", "hello", "team"),
        ("2026-01-01 00:00:01", "Bob", "bye", "all"),
    ]


def test_logger_rejects_writes_after_close(tmp_path: Path):
    db_path = tmp_path / "chat.sqlite"
    logger = MessageLogger(str(db_path))
    logger.close()

    with pytest.raises(RuntimeError):
        logger.log("2026-01-01 00:00:00", "Alice", "hello", "team")


def test_logger_prints_colored_chat_messages(capsys, tmp_path: Path):
    db_path = tmp_path / "chat.sqlite"
    logger = MessageLogger(str(db_path), print_messages=True)

    logger.log("2026-01-01 00:00:00", "Alice", "hello", "team")
    logger.log("2026-01-01 00:00:01", "Bob", "bye", "all")
    logger.close()

    assert capsys.readouterr().out.splitlines() == [
        "\033[38;5;117m2026-01-01 00:00:00 | TEAM | Alice: hello\033[0m",
        "\033[38;5;214m2026-01-01 00:00:01 | ALL  | Bob: bye\033[0m",
    ]


def test_logger_prints_green_hero_tracking_messages(capsys, tmp_path: Path):
    db_path = tmp_path / "hero.sqlite"
    logger = MessageLogger(
        str(db_path),
        print_messages=True,
        print_mode="hero",
        include_chat_type=False,
    )

    logger.log("2026-01-01 00:00:02", "Alice", "Mercy", "team")
    logger.close()

    assert capsys.readouterr().out.splitlines() == [
        "\033[38;5;77m2026-01-01 00:00:02 | HERO | Alice / Mercy\033[0m",
    ]


def test_hero_logger_writes_hero_source_rows(tmp_path: Path):
    db_path = tmp_path / "hero.sqlite"
    logger = MessageLogger(str(db_path), print_mode="hero", include_chat_type=False)

    logger.log("2026-01-01 00:00:02", "Alice", "Mercy", "team")
    logger.close()

    # The hero logger ignores the caller-supplied ``chat_type`` and always
    # writes ``source='hero'``. The ``text`` column carries the hero name.
    assert _read_messages(db_path) == [
        ("2026-01-01 00:00:02", "Alice", "Mercy", "hero"),
    ]


def test_chat_logger_requires_chat_type(tmp_path: Path):
    db_path = tmp_path / "chat.sqlite"
    logger = MessageLogger(str(db_path))

    with pytest.raises(ValueError):
        logger.log("2026-01-01 00:00:00", "Alice", "hello")


def test_chat_logger_rejects_invalid_chat_type(tmp_path: Path):
    """Bad ``chat_type`` is rejected at write time (CHECK constraint
    additionally guards the DB, but the validation is in Python so we get
    a clear ValueError instead of a sqlite3 IntegrityError)."""
    db_path = tmp_path / "chat.sqlite"
    logger = MessageLogger(str(db_path))

    with pytest.raises(ValueError):
        logger.log("2026-01-01 00:00:00", "Alice", "hello", "garbage")
    # The 'hero' label belongs to the hero logger; the chat logger refuses.
    with pytest.raises(ValueError):
        logger.log("2026-01-01 00:00:00", "Alice", "hello", "hero")


def test_chat_and_hero_loggers_share_one_db(tmp_path: Path):
    """Both loggers point at the same DB; rows are split by ``source``."""
    db_path = tmp_path / "chat.sqlite"
    chat = MessageLogger(str(db_path))
    hero = MessageLogger(str(db_path), print_mode="hero", include_chat_type=False)

    chat.log("2026-01-01 00:00:00", "Alice", "hi", "team")
    hero.log("2026-01-01 00:00:01", "Alice", "Mercy")
    chat.close()
    hero.close()

    rows = _read_messages(db_path)
    assert rows == [
        ("2026-01-01 00:00:00", "Alice", "hi", "team"),
        ("2026-01-01 00:00:01", "Alice", "Mercy", "hero"),
    ]
