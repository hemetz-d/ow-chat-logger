import csv
from pathlib import Path

import pytest

from ow_chat_logger.logger import MessageLogger


def test_logger_writes_multiple_rows_and_flushes():
    log_dir = Path(__file__).resolve().parent / "_tmp_logger"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / "chat.csv"
    if log_path.exists():
        log_path.unlink()
    logger = MessageLogger(str(log_path))

    logger.log("2026-01-01 00:00:00", "Alice", "hello", "team")
    logger.log("2026-01-01 00:00:01", "Bob", "bye", "all")
    logger.flush()
    logger.close()

    with log_path.open(newline="", encoding="utf-8") as fh:
        rows = list(csv.reader(fh))

    assert rows == [
        ["2026-01-01 00:00:00", "Alice", "hello", "team"],
        ["2026-01-01 00:00:01", "Bob", "bye", "all"],
    ]


def test_logger_rejects_writes_after_close():
    log_dir = Path(__file__).resolve().parent / "_tmp_logger_closed"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / "chat.csv"
    if log_path.exists():
        log_path.unlink()
    logger = MessageLogger(str(log_path))
    logger.close()

    with pytest.raises(RuntimeError):
        logger.log("2026-01-01 00:00:00", "Alice", "hello", "team")


def test_logger_prints_colored_chat_messages(capsys):
    log_dir = Path(__file__).resolve().parent / "_tmp_logger_prints"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / "chat.csv"
    if log_path.exists():
        log_path.unlink()
    logger = MessageLogger(str(log_path), print_messages=True)

    logger.log("2026-01-01 00:00:00", "Alice", "hello", "team")
    logger.log("2026-01-01 00:00:01", "Bob", "bye", "all")
    logger.close()

    assert capsys.readouterr().out.splitlines() == [
        "\033[38;5;117m2026-01-01 00:00:00 | TEAM | Alice: hello\033[0m",
        "\033[38;5;214m2026-01-01 00:00:01 | ALL  | Bob: bye\033[0m",
    ]


def test_logger_prints_green_hero_tracking_messages(capsys):
    log_dir = Path(__file__).resolve().parent / "_tmp_logger_hero_prints"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / "hero.csv"
    if log_path.exists():
        log_path.unlink()
    logger = MessageLogger(
        str(log_path),
        print_messages=True,
        print_mode="hero",
        include_chat_type=False,
    )

    logger.log("2026-01-01 00:00:02", "Alice", "Mercy", "team")
    logger.close()

    assert capsys.readouterr().out.splitlines() == [
        "\033[38;5;77m2026-01-01 00:00:02 | HERO | Alice / Mercy\033[0m",
    ]


def test_hero_logger_writes_three_column_rows():
    log_dir = Path(__file__).resolve().parent / "_tmp_logger_hero_rows"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / "hero.csv"
    if log_path.exists():
        log_path.unlink()
    logger = MessageLogger(str(log_path), print_mode="hero", include_chat_type=False)

    logger.log("2026-01-01 00:00:02", "Alice", "Mercy", "team")
    logger.close()

    with log_path.open(newline="", encoding="utf-8") as fh:
        rows = list(csv.reader(fh))

    assert rows == [["2026-01-01 00:00:02", "Alice", "Mercy"]]


def test_chat_logger_requires_chat_type():
    log_dir = Path(__file__).resolve().parent / "_tmp_logger_missing_chat_type"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / "chat.csv"
    if log_path.exists():
        log_path.unlink()
    logger = MessageLogger(str(log_path))

    with pytest.raises(ValueError):
        logger.log("2026-01-01 00:00:00", "Alice", "hello")
