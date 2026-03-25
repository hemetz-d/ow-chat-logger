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
