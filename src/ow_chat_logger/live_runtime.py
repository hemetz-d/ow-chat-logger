from __future__ import annotations

import threading
import time
import traceback
from pathlib import Path
from queue import Empty, Full, Queue
from typing import Any

import numpy as np
import pyautogui

from ow_chat_logger.buffer import MessageBuffer
from ow_chat_logger.config import CONFIG, get_app_paths
from ow_chat_logger.deduplication import DuplicateFilter
from ow_chat_logger.logger import MessageLogger
from ow_chat_logger.message_processing import flush_buffers, process_lines
from ow_chat_logger.metrics import PerformanceMetrics
from ow_chat_logger.ocr_engine import OCREngine
from ow_chat_logger.pipeline import extract_chat_debug_data


class LatestFrameQueue:
    """Bounded frame queue that always keeps the freshest screenshots."""

    def __init__(self, maxsize: int = 2):
        self._queue = Queue(maxsize=maxsize)

    def put_latest(self, item) -> int:
        dropped = 0
        while True:
            try:
                self._queue.put_nowait(item)
                return dropped
            except Full:
                try:
                    self._queue.get_nowait()
                    dropped += 1
                except Empty:
                    continue

    def get(self, timeout: float):
        return self._queue.get(timeout=timeout)

    def get_nowait(self):
        return self._queue.get_nowait()

    def empty(self) -> bool:
        return self._queue.empty()


def capture():
    return np.array(pyautogui.screenshot(region=CONFIG["screen_region"]))


def resolve_metrics_log_path(path_value: str | None) -> Path:
    paths = get_app_paths()
    if not path_value:
        return paths.log_dir / "performance_metrics.csv"

    path = Path(path_value).expanduser()
    if path.is_absolute():
        return path
    return paths.log_dir / path


def create_metrics_collector(
    *,
    metrics_enabled_override: bool | None = None,
    metrics_interval_override: float | None = None,
    metrics_log_path_override: str | None = None,
) -> PerformanceMetrics | None:
    enabled = CONFIG.get("metrics_enabled", False)
    if metrics_enabled_override is not None:
        enabled = metrics_enabled_override
    if not enabled:
        return None

    interval_seconds = CONFIG.get("metrics_interval_seconds", 10.0)
    if metrics_interval_override is not None:
        interval_seconds = metrics_interval_override

    log_path = metrics_log_path_override
    if log_path is None:
        log_path = CONFIG.get("metrics_log_path")

    return PerformanceMetrics(
        resolve_metrics_log_path(log_path),
        interval_seconds=interval_seconds,
        capture_interval=CONFIG["capture_interval"],
        use_gpu=CONFIG.get("use_gpu", True),
        screen_region=CONFIG["screen_region"],
    )


def write_crash_log(exc: BaseException) -> None:
    """Append a crash traceback to the configured crash log file."""
    crash_log_path = get_app_paths().crash_log
    crash_log_path.parent.mkdir(parents=True, exist_ok=True)

    with crash_log_path.open("a", encoding="utf-8") as f:
        f.write("--- Crash on {} ---\n".format(time.strftime("%Y-%m-%dT%H:%M:%S")))
        f.write("".join(traceback.format_exception(type(exc), exc, exc.__traceback__)))
        f.write("\n")


def should_run_ocr(mask: np.ndarray, config: dict[str, Any] | None = None) -> bool:
    cfg = CONFIG if config is None else config
    min_nonzero = max(int(cfg.get("min_mask_nonzero_pixels_for_ocr", 0)), 0)
    if min_nonzero == 0:
        return True
    return int(np.count_nonzero(mask)) >= min_nonzero


def extract_chat_lines_for_live(
    screenshot: np.ndarray,
    ocr: OCREngine,
    metrics=None,
) -> dict[str, list[str]]:
    started = time.perf_counter()
    debug_data = extract_chat_debug_data(
        screenshot,
        ocr,
        should_run_ocr=should_run_ocr,
    )
    if metrics is not None:
        timings = debug_data["timings"]
        metrics.record_processed_frame(
            preprocess_seconds=timings["preprocess_seconds"],
            ocr_seconds=timings["ocr_seconds"],
            parse_seconds=timings["parse_seconds"],
            total_seconds=time.perf_counter() - started,
            team_skipped=debug_data["ocr_skipped"]["team"],
            all_skipped=debug_data["ocr_skipped"]["all"],
            team_boxes=len(debug_data["ocr_results"]["team"]),
            all_boxes=len(debug_data["ocr_results"]["all"]),
            team_lines=len(debug_data["raw_lines"]["team"]),
            all_lines=len(debug_data["raw_lines"]["all"]),
        )
    return debug_data["raw_lines"]


def capture_worker(frame_queue, stop_event, error_queue, *, metrics=None) -> None:
    interval = max(float(CONFIG["capture_interval"]), 0.0)
    next_capture = time.monotonic()

    try:
        while not stop_event.is_set():
            now = time.monotonic()
            if now < next_capture and stop_event.wait(next_capture - now):
                break

            capture_started = time.perf_counter()
            screenshot = capture()
            capture_seconds = time.perf_counter() - capture_started
            dropped_frames = frame_queue.put_latest(screenshot)
            if metrics is not None:
                metrics.record_capture(capture_seconds, dropped_frames=dropped_frames)
                metrics.flush_if_due()

            now = time.monotonic()
            if interval == 0:
                next_capture = now
            else:
                next_capture = max(next_capture + interval, now)
    except Exception as exc:
        error_queue.put(exc)
        stop_event.set()


def processing_worker(
    frame_queue,
    stop_event,
    error_queue,
    *,
    ocr,
    team_buffer,
    all_buffer,
    chat_dedup,
    hero_dedup,
    chat_logger,
    hero_logger,
    metrics=None,
) -> None:
    try:
        while not stop_event.is_set() or not frame_queue.empty():
            try:
                if stop_event.is_set():
                    screenshot = frame_queue.get_nowait()
                else:
                    screenshot = frame_queue.get(timeout=0.1)
            except Empty:
                continue

            lines_by_channel = extract_chat_lines_for_live(screenshot, ocr, metrics=metrics)
            process_lines(
                lines_by_channel,
                team_buffer,
                all_buffer,
                chat_dedup=chat_dedup,
                hero_dedup=hero_dedup,
                chat_logger=chat_logger,
                hero_logger=hero_logger,
                metrics=metrics,
            )
            if metrics is not None:
                metrics.flush_if_due()
    except Exception as exc:
        error_queue.put(exc)
        stop_event.set()


def close_loggers(*loggers) -> None:
    for logger in loggers:
        logger.close()


def run_live_logger(
    *,
    metrics_enabled_override: bool | None = None,
    metrics_interval_override: float | None = None,
    metrics_log_path_override: str | None = None,
) -> int:
    ocr = OCREngine(
        CONFIG["languages"],
        CONFIG["confidence_threshold"],
        CONFIG["text_threshold"],
        use_gpu=CONFIG.get("use_gpu", True),
    )

    chat_dedup = DuplicateFilter(CONFIG["max_remembered"])
    hero_dedup = DuplicateFilter(CONFIG["max_remembered"])

    paths = get_app_paths()
    hero_logger = MessageLogger(str(paths.hero_log))
    chat_logger = MessageLogger(str(paths.chat_log), print_messages=True)

    team_buffer = MessageBuffer()
    all_buffer = MessageBuffer()
    frame_queue = LatestFrameQueue()
    stop_event = threading.Event()
    error_queue = Queue()
    metrics = create_metrics_collector(
        metrics_enabled_override=metrics_enabled_override,
        metrics_interval_override=metrics_interval_override,
        metrics_log_path_override=metrics_log_path_override,
    )

    capture_thread = threading.Thread(
        target=capture_worker,
        args=(frame_queue, stop_event, error_queue),
        kwargs={"metrics": metrics},
        name="capture-worker",
        daemon=True,
    )
    processing_thread = threading.Thread(
        target=processing_worker,
        args=(frame_queue, stop_event, error_queue),
        kwargs={
            "ocr": ocr,
            "team_buffer": team_buffer,
            "all_buffer": all_buffer,
            "chat_dedup": chat_dedup,
            "hero_dedup": hero_dedup,
            "chat_logger": chat_logger,
            "hero_logger": hero_logger,
            "metrics": metrics,
        },
        name="processing-worker",
        daemon=True,
    )

    print("ChatOCR running... Ctrl+C to stop.")

    try:
        try:
            capture_thread.start()
            processing_thread.start()

            while True:
                if not error_queue.empty():
                    raise error_queue.get()
                time.sleep(0.1)

        except KeyboardInterrupt:
            print("\nStopping ChatOCR. Goodbye!\n")
        except Exception as exc:
            print("\nUnexpected error. Writing crash log and exiting.\n")
            write_crash_log(exc)
    finally:
        stop_event.set()
        capture_thread.join(timeout=1.0)
        processing_thread.join(timeout=1.0)
        flush_buffers(
            team_buffer,
            all_buffer,
            chat_dedup=chat_dedup,
            hero_dedup=hero_dedup,
            chat_logger=chat_logger,
            hero_logger=hero_logger,
            metrics=metrics,
        )
        chat_logger.flush()
        hero_logger.flush()
        if metrics is not None:
            metrics.close()
        close_loggers(chat_logger, hero_logger)
    return 0
