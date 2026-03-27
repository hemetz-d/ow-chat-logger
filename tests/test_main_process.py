"""Tests for main-loop helpers and _process_finished side effects."""

import json
import threading
from pathlib import Path
from queue import Queue
from unittest.mock import MagicMock
from uuid import uuid4

import numpy as np
import pytest

from ow_chat_logger.buffer import MessageBuffer
from ow_chat_logger.main import (
    CONFIG as MAIN_CONFIG,
    LatestFrameQueue,
    _should_run_ocr,
    _create_metrics_collector,
    _extract_chat_lines_for_live,
    collect_screenshot_messages,
    main,
    _process_finished,
    _process_lines,
    _run_analyze,
    _processing_worker,
)


def _local_tmp_dir(name: str) -> Path:
    path = Path("tests") / "_test_log_dir" / f"{name}-{uuid4().hex}"
    path.mkdir(parents=True, exist_ok=True)
    return path


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

    assert frame_queue.put_latest("first") == 0
    assert frame_queue.put_latest("second") == 0
    assert frame_queue.put_latest("third") == 1

    assert frame_queue.get(timeout=0.01) == "second"
    assert frame_queue.get(timeout=0.01) == "third"


def test_processing_worker_drains_queue_after_stop(monkeypatch):
    processed = []

    def fake_extract_chat_lines(screenshot, ocr, metrics=None):
        processed.append(screenshot)
        return {"team": ["[Alice] : hi"], "all": []}

    monkeypatch.setattr("ow_chat_logger.main._extract_chat_lines_for_live", fake_extract_chat_lines)

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


def test_collect_screenshot_messages_reuses_app_filtering_rules():
    actual = collect_screenshot_messages(
        {
            "team": [
                "Joined team voice chat - Push to talk",
                "MiniNinja (Bastion): We need a healer",
            ],
            "all": [
                "7",
                "[Smokeelite3] : that was embarrassing",
            ],
        }
    )

    assert actual == {
        "team_lines": [],
        "all_lines": ["[Smokeelite3]: that was embarrassing"],
    }


def test_collect_screenshot_messages_can_include_hero_lines():
    actual = collect_screenshot_messages(
        {
            "team": ["MiniNinja (Bastion): We need a healer"],
            "all": [],
        },
        include_hero_lines=True,
    )

    assert actual == {
        "team_lines": ["MiniNinja (Bastion): We need a healer"],
        "all_lines": [],
    }


def test_collect_screenshot_messages_strips_trailing_report_suffix():
    actual = collect_screenshot_messages(
        {
            "team": [],
            "all": ["[Smokeelite3] : offensive message [Report]"],
        }
    )

    assert actual == {
        "team_lines": [],
        "all_lines": ["[Smokeelite3]: offensive message"],
    }


def test_collect_screenshot_messages_strips_report_suffix_for_hero_lines_when_enabled():
    actual = collect_screenshot_messages(
        {
            "team": ["MiniNinja (Bastion): We need a healer [Report]"],
            "all": [],
        },
        include_hero_lines=True,
    )

    assert actual == {
        "team_lines": ["MiniNinja (Bastion): We need a healer"],
        "all_lines": [],
    }


def test_main_without_args_dispatches_to_live_logger(monkeypatch):
    called = {}

    def fake_run_live_logger(**kwargs):
        called.update(kwargs)
        return 7

    monkeypatch.setattr("ow_chat_logger.main.run_live_logger", fake_run_live_logger)

    assert main([]) == 7
    assert called == {
        "metrics_enabled_override": None,
        "metrics_interval_override": None,
        "metrics_log_path_override": None,
    }


def test_main_metrics_flags_dispatch_to_live_logger(monkeypatch):
    called = {}

    def fake_run_live_logger(**kwargs):
        called.update(kwargs)
        return 13

    monkeypatch.setattr("ow_chat_logger.main.run_live_logger", fake_run_live_logger)

    assert main(["--metrics", "--metrics-interval", "5", "--metrics-log-path", "perf.csv"]) == 13
    assert called == {
        "metrics_enabled_override": True,
        "metrics_interval_override": 5.0,
        "metrics_log_path_override": "perf.csv",
    }


def test_main_analyze_dispatches(monkeypatch):
    tmp_dir = _local_tmp_dir("analyze-dispatch")
    image_path = tmp_dir / "sample.png"
    image_path.write_bytes(b"fake")
    called = []

    def fake_run_analyze(args):
        called.append(args.image)
        return 11

    monkeypatch.setattr("ow_chat_logger.main._run_analyze", fake_run_analyze)

    assert main(["analyze", "--image", str(image_path)]) == 11
    assert called == [str(image_path)]


def test_create_metrics_collector_disabled_by_default():
    assert _create_metrics_collector() is None


def test_should_run_ocr_uses_nonzero_threshold():
    mask = np.zeros((3, 3), dtype=np.uint8)
    mask[0, 0] = 255
    mask[0, 1] = 255

    assert _should_run_ocr(mask, {"min_mask_nonzero_pixels_for_ocr": 2}) is True
    assert _should_run_ocr(mask, {"min_mask_nonzero_pixels_for_ocr": 3}) is False


def test_extract_chat_lines_for_live_records_metrics(monkeypatch):
    screenshot = np.zeros((2, 2, 3), dtype=np.uint8)
    recorded = {}

    monkeypatch.setattr(
        "ow_chat_logger.main.create_chat_masks",
        lambda image, config: (np.ones((2, 2), dtype=np.uint8), np.ones((2, 2), dtype=np.uint8)),
    )
    monkeypatch.setattr("ow_chat_logger.main.clean_mask", lambda mask, config: mask)
    monkeypatch.setattr("ow_chat_logger.main.reconstruct_lines", lambda results, config: [results[0][1]] if results else [])
    monkeypatch.setitem(MAIN_CONFIG, "min_mask_nonzero_pixels_for_ocr", 1)

    class FakeOCR:
        def __init__(self):
            self.calls = 0

        def run(self, mask):
            self.calls += 1
            return [([[0, 0], [1, 0], [1, 1], [0, 1]], f"text-{self.calls}", 0.99)]

    class FakeMetrics:
        def record_processed_frame(self, **kwargs):
            recorded.update(kwargs)

    lines = _extract_chat_lines_for_live(screenshot, FakeOCR(), metrics=FakeMetrics())

    assert lines == {"team": ["text-1"], "all": ["text-2"]}
    assert recorded["team_skipped"] is False
    assert recorded["all_skipped"] is False
    assert recorded["team_boxes"] == 1
    assert recorded["all_boxes"] == 1
    assert recorded["team_lines"] == 1
    assert recorded["all_lines"] == 1


def test_extract_chat_lines_for_live_skips_ocr_for_nearly_empty_masks(monkeypatch):
    screenshot = np.zeros((2, 2, 3), dtype=np.uint8)

    monkeypatch.setattr(
        "ow_chat_logger.main.create_chat_masks",
        lambda image, config: (
            np.array([[255, 0], [0, 0]], dtype=np.uint8),
            np.array([[255, 255], [0, 0]], dtype=np.uint8),
        ),
    )
    monkeypatch.setattr("ow_chat_logger.main.clean_mask", lambda mask, config: mask)
    monkeypatch.setattr("ow_chat_logger.main.reconstruct_lines", lambda results, config: [result[1] for result in results])
    monkeypatch.setitem(MAIN_CONFIG, "min_mask_nonzero_pixels_for_ocr", 2)

    class FakeOCR:
        def __init__(self):
            self.calls = 0

        def run(self, mask):
            self.calls += 1
            return [([[0, 0], [1, 0], [1, 1], [0, 1]], f"text-{self.calls}", 0.99)]

    ocr = FakeOCR()
    lines = _extract_chat_lines_for_live(screenshot, ocr)

    assert ocr.calls == 1
    assert lines == {"team": [], "all": ["text-1"]}


def test_extract_chat_lines_for_live_records_skip_flags(monkeypatch):
    screenshot = np.zeros((2, 2, 3), dtype=np.uint8)
    recorded = {}

    monkeypatch.setattr(
        "ow_chat_logger.main.create_chat_masks",
        lambda image, config: (
            np.array([[255, 0], [0, 0]], dtype=np.uint8),
            np.array([[255, 255], [0, 0]], dtype=np.uint8),
        ),
    )
    monkeypatch.setattr("ow_chat_logger.main.clean_mask", lambda mask, config: mask)
    monkeypatch.setattr("ow_chat_logger.main.reconstruct_lines", lambda results, config: [result[1] for result in results])
    monkeypatch.setitem(MAIN_CONFIG, "min_mask_nonzero_pixels_for_ocr", 2)

    class FakeOCR:
        def run(self, mask):
            return [([[0, 0], [1, 0], [1, 1], [0, 1]], "text", 0.99)]

    class FakeMetrics:
        def record_processed_frame(self, **kwargs):
            recorded.update(kwargs)

    _extract_chat_lines_for_live(screenshot, FakeOCR(), metrics=FakeMetrics())

    assert recorded["team_skipped"] is True
    assert recorded["all_skipped"] is False


def test_main_analyze_requires_image():
    with pytest.raises(SystemExit):
        main(["analyze"])


def test_run_analyze_writes_report_and_masks(monkeypatch):
    tmp_dir = _local_tmp_dir("analyze-artifacts")
    output_dir = tmp_dir / "analysis"
    image_path = tmp_dir / "sample.png"
    image_path.write_bytes(b"placeholder")
    rgb_image = np.zeros((2, 2, 3), dtype=np.uint8)

    monkeypatch.setattr("ow_chat_logger.main._load_rgb_image", lambda path: rgb_image)
    monkeypatch.setattr("ow_chat_logger.main.OCREngine", lambda *args, **kwargs: object())
    monkeypatch.setattr(
        "ow_chat_logger.main.extract_chat_debug_data",
        lambda image, ocr, config_overrides=None: {
            "config": {
                "languages": ["en"],
                "confidence_threshold": 0.7,
                "text_threshold": 0.5,
                "scale_factor": 3,
                "y_merge_threshold": 18,
                "team_hsv_lower": [1, 2, 3],
                "team_hsv_upper": [4, 5, 6],
                "all_hsv_lower": [7, 8, 9],
                "all_hsv_upper": [10, 11, 12],
                "use_gpu": False,
            },
            "cropped_rgb_image": rgb_image,
            "masks": {
                "team": np.zeros((2, 2), dtype=np.uint8),
                "all": np.ones((2, 2), dtype=np.uint8),
            },
            "raw_lines": {
                "team": ["[Alice] : hi there"],
                "all": ["Joined team voice chat - Push to talk", "[Bob] : hello"],
            },
        },
    )

    args = MagicMock(image=str(image_path), output_dir=str(output_dir), config=None)
    assert _run_analyze(args) == 0

    report = json.loads((output_dir / "report.json").read_text(encoding="utf-8"))
    assert report["raw_lines"]["team"] == ["[Alice] : hi there"]
    assert report["final_lines"] == {
        "team_lines": ["[Alice]: hi there"],
        "all_lines": ["[Bob]: hello"],
    }
    assert Path(report["artifacts"]["original_image"]).is_file()
    assert Path(report["artifacts"]["team_mask"]).is_file()
    assert Path(report["artifacts"]["all_mask"]).is_file()


def test_run_analyze_honors_json_overrides(monkeypatch):
    tmp_dir = _local_tmp_dir("analyze-overrides")
    image_path = tmp_dir / "sample.png"
    image_path.write_bytes(b"placeholder")
    config_path = tmp_dir / "override.json"
    config_path.write_text(
        json.dumps(
            {
                "languages": ["de"],
                "confidence_threshold": 0.25,
                "text_threshold": 0.33,
                "use_gpu": False,
            }
        ),
        encoding="utf-8",
    )

    created = {}
    monkeypatch.setattr("ow_chat_logger.main._load_rgb_image", lambda path: np.zeros((1, 1, 3), dtype=np.uint8))

    def fake_ocr(languages, confidence_threshold, text_threshold, use_gpu=True):
        created["languages"] = languages
        created["confidence_threshold"] = confidence_threshold
        created["text_threshold"] = text_threshold
        created["use_gpu"] = use_gpu
        return object()

    monkeypatch.setattr("ow_chat_logger.main.OCREngine", fake_ocr)
    monkeypatch.setattr(
        "ow_chat_logger.main.extract_chat_debug_data",
        lambda image, ocr, config_overrides=None: {
            "config": {**config_overrides},
            "cropped_rgb_image": image,
            "masks": {
                "team": np.zeros((1, 1), dtype=np.uint8),
                "all": np.zeros((1, 1), dtype=np.uint8),
            },
            "raw_lines": {"team": [], "all": []},
        },
    )

    args = MagicMock(
        image=str(image_path),
        output_dir=str(tmp_dir / "out"),
        config=str(config_path),
    )
    _run_analyze(args)

    assert created == {
        "languages": ["de"],
        "confidence_threshold": 0.25,
        "text_threshold": 0.33,
        "use_gpu": False,
    }


def test_run_analyze_report_matches_existing_regression_expectation(monkeypatch):
    tmp_dir = _local_tmp_dir("analyze-regression")
    fixture_path = tmp_dir / "fixture.png"
    fixture_path.write_bytes(b"placeholder")
    expected_path = (
        Path(__file__).resolve().parent / "fixtures" / "regression" / "example_1.expected.json"
    )
    expected = json.loads(expected_path.read_text(encoding="utf-8"))

    monkeypatch.setattr("ow_chat_logger.main._load_rgb_image", lambda path: np.zeros((1, 1, 3), dtype=np.uint8))
    monkeypatch.setattr("ow_chat_logger.main.OCREngine", lambda *args, **kwargs: object())
    monkeypatch.setattr(
        "ow_chat_logger.main.extract_chat_debug_data",
        lambda image, ocr, config_overrides=None: {
            "config": {},
            "cropped_rgb_image": image,
            "masks": {
                "team": np.zeros((1, 1), dtype=np.uint8),
                "all": np.zeros((1, 1), dtype=np.uint8),
            },
            "raw_lines": {
                "team": ["[FrankShoe] : gg team no heals"],
                "all": [
                    "[Smokeelite3] : lads what the hell are yous doing",
                    "[Smokeelite3] : that was embarassing",
                    "[MrHenderson] : you guys suck baalls",
                ],
            },
        },
    )

    output_dir = tmp_dir / "analysis"
    args = MagicMock(image=str(fixture_path), output_dir=str(output_dir), config=None)
    _run_analyze(args)

    report = json.loads((output_dir / "report.json").read_text(encoding="utf-8"))
    assert report["final_lines"] == expected
