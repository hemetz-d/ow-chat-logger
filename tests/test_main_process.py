"""Tests for main-loop helpers and _process_finished side effects."""

import threading
from queue import Queue
from unittest.mock import MagicMock

from ow_chat_logger.buffer import MessageBuffer
from ow_chat_logger.main import (
    LatestFrameQueue,
    _process_finished,
    _process_lines,
    _processing_worker,
)


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


def test_latest_frame_queue_drops_oldest_item():
    frame_queue = LatestFrameQueue(maxsize=2)

    frame_queue.put_latest("first")
    frame_queue.put_latest("second")
    frame_queue.put_latest("third")

    assert frame_queue.get(timeout=0.01) == "second"
    assert frame_queue.get(timeout=0.01) == "third"


def test_processing_worker_drains_queue_after_stop(monkeypatch):
    processed = []

    def fake_extract_chat_lines(screenshot, ocr):
        processed.append(screenshot)
        return {"team": ["[Alice] : hi"], "all": []}

    monkeypatch.setattr("ow_chat_logger.main.extract_chat_lines", fake_extract_chat_lines)

    frame_queue = LatestFrameQueue(maxsize=2)
    frame_queue.put_latest("frame-1")
    frame_queue.put_latest("frame-2")

    stop_event = threading.Event()
    stop_event.set()
    error_queue = Queue()
    chat_logger = MagicMock()

    _processing_worker(
        frame_queue,
        stop_event,
        error_queue,
        ocr=MagicMock(),
        team_buffer=MessageBuffer(),
        all_buffer=MessageBuffer(),
        chat_dedup=MagicMock(is_new=MagicMock(return_value=True)),
        hero_dedup=MagicMock(),
        chat_logger=chat_logger,
        hero_logger=MagicMock(),
    )

    assert error_queue.empty()
    assert processed == ["frame-1", "frame-2"]
    assert chat_logger.log.call_count == 2


def test_process_lines_does_not_carry_continuation_between_screenshots():
    chat_logger = MagicMock()
    team_buffer = MessageBuffer()
    all_buffer = MessageBuffer()
    chat_dedup = MagicMock()
    chat_dedup.is_new.return_value = True

    _process_lines(
        {"team": ["[Alice] : hello"], "all": []},
        team_buffer,
        all_buffer,
        chat_dedup=chat_dedup,
        hero_dedup=MagicMock(),
        chat_logger=chat_logger,
        hero_logger=MagicMock(),
    )

    _process_lines(
        {"team": ["continued text"], "all": []},
        team_buffer,
        all_buffer,
        chat_dedup=chat_dedup,
        hero_dedup=MagicMock(),
        chat_logger=chat_logger,
        hero_logger=MagicMock(),
    )

    assert chat_logger.log.call_count == 1
