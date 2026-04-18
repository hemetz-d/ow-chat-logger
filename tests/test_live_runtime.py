import threading
from pathlib import Path
from queue import Queue
from unittest.mock import MagicMock

import numpy as np

from ow_chat_logger.buffer import MessageBuffer
from ow_chat_logger.config import CONFIG
from ow_chat_logger.live_runtime import (
    LiveRecordConfirmationGate,
    LatestFrameQueue,
    build_live_startup_banner,
    create_metrics_collector,
    default_metrics_log_name,
    extract_chat_lines_for_live,
    processing_worker,
    resolve_metrics_log_path,
    should_run_ocr,
)
from ow_chat_logger.ocr import ResolvedOCRProfile


def test_latest_frame_queue_drops_oldest_item():
    frame_queue = LatestFrameQueue(maxsize=2)

    assert frame_queue.put_latest("first") == 0
    assert frame_queue.put_latest("second") == 0
    assert frame_queue.put_latest("third") == 1

    assert frame_queue.get(timeout=0.01) == "second"
    assert frame_queue.get(timeout=0.01) == "third"


def test_processing_worker_drains_queue_after_stop(monkeypatch):
    processed = []
    import ow_chat_logger.config as cfg_module

    cfg_module.load_config()
    monkeypatch.setitem(cfg_module._cached_config, "live_message_confirmations_required", 1)

    def fake_extract_chat_debug_data(screenshot, ocr, **kwargs):
        processed.append(screenshot)
        return {
            "raw_lines": {"team": ["[Alice] : hi"], "all": []},
            "raw_line_ys": {"team": [], "all": []},
            "timings": {"preprocess_seconds": 0, "ocr_seconds": 0, "parse_seconds": 0},
            "ocr_skipped": {"team": False, "all": False},
            "ocr_results": {"team": [], "all": []},
        }

    monkeypatch.setattr(
        "ow_chat_logger.live_runtime.extract_chat_debug_data",
        fake_extract_chat_debug_data,
    )

    frame_queue = LatestFrameQueue(maxsize=2)
    frame_queue.put_latest("frame-1")
    frame_queue.put_latest("frame-2")

    stop_event = threading.Event()
    stop_event.set()
    error_queue = Queue()
    chat_logger = MagicMock()

    processing_worker(
        frame_queue,
        stop_event,
        error_queue,
        ocr=MagicMock(),
        ocr_profile=None,
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


def test_live_record_confirmation_gate_requires_two_consecutive_frames():
    gate = LiveRecordConfirmationGate(2)
    record = {
        "category": "standard",
        "chat_type": "team",
        "player": "Alice",
        "msg": "hello",
        "hero": "",
    }

    assert gate.accept_frame([record]) == []
    assert gate.accept_frame([record]) == [record]
    assert gate.accept_frame([record]) == []


def test_live_record_confirmation_gate_supports_hero_records():
    gate = LiveRecordConfirmationGate(2)
    record = {
        "category": "hero",
        "chat_type": "all",
        "player": "Alice",
        "msg": "group up",
        "hero": "Mercy",
    }

    assert gate.accept_frame([record]) == []
    assert gate.accept_frame([record]) == [record]


def test_live_record_confirmation_gate_drops_pending_record_after_gap():
    gate = LiveRecordConfirmationGate(2)
    record = {
        "category": "standard",
        "chat_type": "team",
        "player": "Alice",
        "msg": "hello",
        "hero": "",
    }

    assert gate.accept_frame([record]) == []
    assert gate.accept_frame([]) == []
    assert gate.accept_frame([record]) == []


def test_live_record_confirmation_gate_threshold_one_preserves_immediate_logging():
    gate = LiveRecordConfirmationGate(1)
    record = {
        "category": "standard",
        "chat_type": "team",
        "player": "Alice",
        "msg": "hello",
        "hero": "",
    }

    assert gate.accept_frame([record]) == [record]


def test_live_record_confirmation_gate_clamps_threshold_below_one():
    gate = LiveRecordConfirmationGate(0)
    record = {
        "category": "standard",
        "chat_type": "team",
        "player": "Alice",
        "msg": "hello",
        "hero": "",
    }

    assert gate.accept_frame([record]) == [record]


def test_processing_worker_does_not_log_single_frame_artifact_with_confirmation(monkeypatch):
    import ow_chat_logger.config as cfg_module

    cfg_module.load_config()
    monkeypatch.setitem(cfg_module._cached_config, "live_message_confirmations_required", 2)

    def fake_extract_chat_debug_data(screenshot, ocr, **kwargs):
        return {
            "raw_lines": {"team": ["[Alice] : hi"], "all": []},
            "raw_line_ys": {"team": [], "all": []},
            "timings": {"preprocess_seconds": 0, "ocr_seconds": 0, "parse_seconds": 0},
            "ocr_skipped": {"team": False, "all": False},
            "ocr_results": {"team": [], "all": []},
        }

    monkeypatch.setattr(
        "ow_chat_logger.live_runtime.extract_chat_debug_data",
        fake_extract_chat_debug_data,
    )

    frame_queue = LatestFrameQueue(maxsize=2)
    frame_queue.put_latest("frame-1")
    stop_event = threading.Event()
    stop_event.set()
    error_queue = Queue()
    chat_logger = MagicMock()

    processing_worker(
        frame_queue,
        stop_event,
        error_queue,
        ocr=MagicMock(),
        ocr_profile=None,
        team_buffer=MessageBuffer(),
        all_buffer=MessageBuffer(),
        chat_dedup=MagicMock(is_new=MagicMock(return_value=True)),
        hero_dedup=MagicMock(),
        chat_logger=chat_logger,
        hero_logger=MagicMock(),
    )

    assert error_queue.empty()
    chat_logger.log.assert_not_called()


def test_processing_worker_picks_up_hsv_changes_via_reload_event(monkeypatch):
    """T-42: a mid-session reload signal must make the next frame use the new profile."""
    import ow_chat_logger.config as cfg_module

    cfg_module.load_config()
    monkeypatch.setitem(cfg_module._cached_config, "live_message_confirmations_required", 1)

    observed_profiles: list[ResolvedOCRProfile] = []

    def fake_extract_chat_debug_data(screenshot, ocr, **kwargs):
        observed_profiles.append(kwargs.get("ocr_profile"))
        return {
            "raw_lines": {"team": [], "all": []},
            "raw_line_ys": {"team": [], "all": []},
            "timings": {"preprocess_seconds": 0, "ocr_seconds": 0, "parse_seconds": 0},
            "ocr_skipped": {"team": False, "all": False},
            "ocr_results": {"team": [], "all": []},
        }

    monkeypatch.setattr(
        "ow_chat_logger.live_runtime.extract_chat_debug_data",
        fake_extract_chat_debug_data,
    )

    initial_profile = ResolvedOCRProfile(
        name="windows_default",
        engine_id="windows",
        languages=["en", "de"],
        pipeline={
            "team_hsv_lower": [96, 190, 90],
            "team_hsv_upper": [118, 255, 255],
            "all_hsv_lower": [0, 150, 100],
            "all_hsv_upper": [20, 255, 255],
        },
        settings={},
    )

    frame_queue = LatestFrameQueue(maxsize=4)
    frame_queue.put_latest("frame-pre")
    frame_queue.put_latest("frame-post")

    stop_event = threading.Event()
    stop_event.set()  # drain-only: run until frame queue empties
    error_queue = Queue()
    reload_event = threading.Event()
    reload_notice: Queue = Queue()

    # Simulate the user mutating HSV bounds between frames: the first loop iteration
    # sees the original config; before the second iteration processes, we set the
    # reload_event AND change the cached config so the reload re-resolves fresh.
    mutated_hsv_lower = [10, 20, 30]
    original_extract = fake_extract_chat_debug_data

    call_count = {"n": 0}

    def spying_extract(screenshot, ocr, **kwargs):
        call_count["n"] += 1
        # After the first frame is processed, mutate config + trip the reload flag
        # so the second iteration's reload check picks it up.
        if call_count["n"] == 1:
            cfg_module._cached_config["ocr"]["profiles"]["windows_default"]["pipeline"][
                "team_hsv_lower"
            ] = mutated_hsv_lower
            reload_event.set()
        return original_extract(screenshot, ocr, **kwargs)

    monkeypatch.setattr(
        "ow_chat_logger.live_runtime.extract_chat_debug_data",
        spying_extract,
    )

    processing_worker(
        frame_queue,
        stop_event,
        error_queue,
        ocr=MagicMock(),
        ocr_profile=initial_profile,
        team_buffer=MessageBuffer(),
        all_buffer=MessageBuffer(),
        chat_dedup=MagicMock(is_new=MagicMock(return_value=True)),
        hero_dedup=MagicMock(),
        chat_logger=MagicMock(),
        hero_logger=MagicMock(),
        reload_event=reload_event,
        reload_notice=reload_notice,
    )

    assert error_queue.empty()
    assert len(observed_profiles) == 2
    assert observed_profiles[0].pipeline["team_hsv_lower"] == [96, 190, 90]
    assert observed_profiles[1].pipeline["team_hsv_lower"] == mutated_hsv_lower
    # Engine + languages unchanged, so the swap is silent (no reload_notice items).
    assert reload_notice.empty()


def test_processing_worker_reload_rejects_engine_change_without_restart(monkeypatch):
    """T-42: engine change mid-session must NOT swap the running profile."""
    import ow_chat_logger.config as cfg_module

    cfg_module.load_config()
    monkeypatch.setitem(cfg_module._cached_config, "live_message_confirmations_required", 1)

    observed_profiles: list[ResolvedOCRProfile] = []

    def spying_extract(screenshot, ocr, **kwargs):
        observed_profiles.append(kwargs.get("ocr_profile"))
        return {
            "raw_lines": {"team": [], "all": []},
            "raw_line_ys": {"team": [], "all": []},
            "timings": {"preprocess_seconds": 0, "ocr_seconds": 0, "parse_seconds": 0},
            "ocr_skipped": {"team": False, "all": False},
            "ocr_results": {"team": [], "all": []},
        }

    monkeypatch.setattr(
        "ow_chat_logger.live_runtime.extract_chat_debug_data",
        spying_extract,
    )

    # Running profile claims engine "windows"; simulated reload will return a
    # profile with engine "easyocr" — swap must be refused.
    running_profile = ResolvedOCRProfile(
        name="windows_default",
        engine_id="windows",
        languages=["en", "de"],
        pipeline={"team_hsv_lower": [96, 190, 90]},
        settings={},
    )
    new_profile = ResolvedOCRProfile(
        name="easyocr_master_baseline",
        engine_id="easyocr",
        languages=["en", "de"],
        pipeline={"team_hsv_lower": [1, 2, 3]},
        settings={},
    )
    monkeypatch.setattr(
        "ow_chat_logger.live_runtime.resolve_ocr_profile",
        lambda _cfg=None, _name=None: new_profile,
    )

    frame_queue = LatestFrameQueue(maxsize=4)
    frame_queue.put_latest("frame-pre")
    frame_queue.put_latest("frame-post")
    stop_event = threading.Event()
    stop_event.set()
    error_queue = Queue()
    reload_event = threading.Event()
    reload_event.set()  # trip before first frame so reload fires on iteration 1
    reload_notice: Queue = Queue()

    processing_worker(
        frame_queue,
        stop_event,
        error_queue,
        ocr=MagicMock(),
        ocr_profile=running_profile,
        team_buffer=MessageBuffer(),
        all_buffer=MessageBuffer(),
        chat_dedup=MagicMock(is_new=MagicMock(return_value=True)),
        hero_dedup=MagicMock(),
        chat_logger=MagicMock(),
        hero_logger=MagicMock(),
        reload_event=reload_event,
        reload_notice=reload_notice,
    )

    # Both frames should still see the original running profile — the engine
    # mismatch must prevent the swap.
    assert len(observed_profiles) == 2
    assert all(p is running_profile for p in observed_profiles)


def test_create_metrics_collector_disabled_by_default():
    assert create_metrics_collector() is None


def test_default_metrics_log_name_uses_timestamped_csv_name():
    name = default_metrics_log_name()

    assert name.startswith("performance_metrics_")
    assert name.endswith(".csv")


def test_resolve_metrics_log_path_defaults_to_new_timestamped_file():
    path = resolve_metrics_log_path(None)

    assert path.parent == Path(CONFIG["log_dir"])
    assert path.name.startswith("performance_metrics_")
    assert path.suffix == ".csv"


def test_build_live_startup_banner_includes_user_paths():
    class FakeProfile:
        name = "windows_default"
        engine_id = "windows"

    class FakePaths:
        log_dir = Path("C:/Apps/OW Chat Logger Data")
        chat_log = log_dir / "chat_log.csv"
        hero_log = log_dir / "hero_log.csv"
        config_path = Path("C:/Users/test/AppData/Roaming/ow-chat-logger/config.json")
        crash_log = Path("C:/Users/test/AppData/Roaming/ow-chat-logger/crash.log")

    banner = build_live_startup_banner(profile=FakeProfile(), paths=FakePaths())

    assert "\033[" in banner
    assert "ChatOCR running with profile 'windows_default' (windows)." in banner
    assert "Chat log:    C:\\Apps\\OW Chat Logger Data\\chat_log.csv" in banner
    assert "Hero log:    C:\\Apps\\OW Chat Logger Data\\hero_log.csv" in banner
    assert "Config file: C:\\Users\\test\\AppData\\Roaming\\ow-chat-logger\\config.json" in banner
    assert "Crash log:   C:\\Users\\test\\AppData\\Roaming\\ow-chat-logger\\crash.log" in banner
    assert "Live tracking active." in banner
    assert "Ctrl+C to stop." in banner
    assert "\n\n\033[" in banner
    assert "Output folder:" not in banner
    assert "Paths:" not in banner


def test_should_run_ocr_uses_nonzero_threshold():
    mask = np.zeros((3, 3), dtype=np.uint8)
    mask[0, 0] = 255
    mask[0, 1] = 255

    assert should_run_ocr(mask, {"min_mask_nonzero_pixels_for_ocr": 2}) is True
    assert should_run_ocr(mask, {"min_mask_nonzero_pixels_for_ocr": 3}) is False


def test_extract_chat_lines_for_live_records_metrics(monkeypatch):
    screenshot = np.zeros((2, 2, 3), dtype=np.uint8)
    recorded = {}

    monkeypatch.setattr(
        "ow_chat_logger.live_runtime.extract_chat_debug_data",
        lambda image, ocr, should_run_ocr=None, ocr_profile=None, **kwargs: {
            "timings": {
                "preprocess_seconds": 0.01,
                "ocr_seconds": 0.02,
                "parse_seconds": 0.03,
            },
            "ocr_skipped": {"team": False, "all": False},
            "ocr_results": {"team": [("a", "text-1", 0.99)], "all": [("b", "text-2", 0.99)]},
            "raw_lines": {"team": ["text-1"], "all": ["text-2"]},
        },
    )

    class FakeMetrics:
        def record_processed_frame(self, **kwargs):
            recorded.update(kwargs)

    lines = extract_chat_lines_for_live(screenshot, MagicMock(), metrics=FakeMetrics())

    assert lines == {"team": ["text-1"], "all": ["text-2"]}
    assert recorded["team_skipped"] is False
    assert recorded["all_skipped"] is False
    assert recorded["team_boxes"] == 1
    assert recorded["all_boxes"] == 1
    assert recorded["team_lines"] == 1
    assert recorded["all_lines"] == 1


def test_extract_chat_lines_for_live_skips_ocr_for_nearly_empty_masks(monkeypatch):
    import ow_chat_logger.config as cfg_module

    screenshot = np.zeros((2, 2, 3), dtype=np.uint8)
    cfg_module.load_config()
    monkeypatch.setitem(cfg_module._cached_config, "min_mask_nonzero_pixels_for_ocr", 2)

    def fake_debug_data(image, ocr, should_run_ocr=None, ocr_profile=None, **kwargs):
        team_mask = np.array([[255, 0], [0, 0]], dtype=np.uint8)
        all_mask = np.array([[255, 255], [0, 0]], dtype=np.uint8)
        return {
            "timings": {
                "preprocess_seconds": 0.01,
                "ocr_seconds": 0.02,
                "parse_seconds": 0.03,
            },
            "ocr_skipped": {
                "team": not should_run_ocr(team_mask, CONFIG),
                "all": not should_run_ocr(all_mask, CONFIG),
            },
            "ocr_results": {
                "team": [],
                "all": [("b", "text-1", 0.99)],
            },
            "raw_lines": {
                "team": [],
                "all": ["text-1"],
            },
        }

    monkeypatch.setattr(
        "ow_chat_logger.live_runtime.extract_chat_debug_data",
        fake_debug_data,
    )

    lines = extract_chat_lines_for_live(screenshot, MagicMock())
    assert lines == {"team": [], "all": ["text-1"]}


def test_extract_chat_lines_for_live_records_skip_flags(monkeypatch):
    screenshot = np.zeros((2, 2, 3), dtype=np.uint8)
    recorded = {}

    monkeypatch.setattr(
        "ow_chat_logger.live_runtime.extract_chat_debug_data",
        lambda image, ocr, should_run_ocr=None, ocr_profile=None, **kwargs: {
            "timings": {
                "preprocess_seconds": 0.01,
                "ocr_seconds": 0.02,
                "parse_seconds": 0.03,
            },
            "ocr_skipped": {"team": True, "all": False},
            "ocr_results": {"team": [], "all": [("b", "text", 0.99)]},
            "raw_lines": {"team": [], "all": ["text"]},
        },
    )

    class FakeMetrics:
        def record_processed_frame(self, **kwargs):
            recorded.update(kwargs)

    extract_chat_lines_for_live(screenshot, MagicMock(), metrics=FakeMetrics())

    assert recorded["team_skipped"] is True
    assert recorded["all_skipped"] is False
