"""Tests for _process_finished side effects."""

from unittest.mock import MagicMock

from ow_chat_logger.main import _process_finished


def test_process_finished_standard_logs_once():
    chat_dedup = MagicMock()
    chat_dedup.is_new.return_value = True
    hero_dedup = MagicMock()
    chat_logger = MagicMock()
    hero_logger = MagicMock()

    finished = {
        "category": "standard",
        "player": "Alice",
        "hero": "",
        "msg": "hello",
    }

    _process_finished(
        finished,
        "team",
        chat_dedup=chat_dedup,
        hero_dedup=hero_dedup,
        chat_logger=chat_logger,
        hero_logger=hero_logger,
    )

    chat_logger.log.assert_called_once()
    hero_logger.log.assert_not_called()
    assert chat_dedup.is_new.called


def test_process_finished_ignores_ignored_senders():
    chat_logger = MagicMock()
    _process_finished(
        {
            "category": "standard",
            "player": "team",
            "hero": "",
            "msg": "spam",
        },
        "all",
        chat_dedup=MagicMock(),
        hero_dedup=MagicMock(),
        chat_logger=chat_logger,
        hero_logger=MagicMock(),
    )
    chat_logger.log.assert_not_called()


def test_process_finished_none_noop():
    chat_logger = MagicMock()
    _process_finished(
        None,
        "team",
        chat_dedup=MagicMock(),
        hero_dedup=MagicMock(),
        chat_logger=chat_logger,
        hero_logger=MagicMock(),
    )
    chat_logger.log.assert_not_called()
