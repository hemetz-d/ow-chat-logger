from __future__ import annotations

import datetime
import threading
import time
import traceback
from pathlib import Path
from queue import Empty, Full, Queue
from typing import Any

import numpy as np
import pyautogui

from ow_chat_logger.buffer import MessageBuffer
from ow_chat_logger.config import CONFIG, get_app_paths, resolve_ocr_profile
from ow_chat_logger.debug_snaps import (
    build_allowed_charset,
    contains_suspicious_characters,
    has_bboxes_without_lines,
    message_contains_embedded_prefix,
    save_anomaly_snapshot,
    suspicious_chars_in,
)
from ow_chat_logger.deduplication import DuplicateFilter
from ow_chat_logger.logger import MessageLogger, colorize_console_text
from ow_chat_logger.message_processing import (
    collect_normalized_records,
    flush_buffers,
    log_normalized_record,
)
from ow_chat_logger.metrics import PerformanceMetrics
from ow_chat_logger.ocr import OCRBackend, ResolvedOCRProfile, build_ocr_backend
from ow_chat_logger.pipeline import extract_chat_debug_data

BANNER_HEADER_COLOR = "\033[38;5;81m"
BANNER_PATHS_COLOR = "\033[38;5;110m"
BANNER_SECONDARY_COLOR = "\033[38;5;245m"
BANNER_READY_COLOR = "\033[38;5;121m"
BANNER_STOP_COLOR = "\033[38;5;229m"


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


class LiveRecordConfirmationGate:
    """Require consistent records across consecutive processed frames before logging."""

    def __init__(self, required_confirmations: int):
        self.required_confirmations = max(int(required_confirmations), 1)
        self._pending_counts: dict[tuple[Any, ...], int] = {}
        self._committed_active: set[tuple[Any, ...]] = set()

    @staticmethod
    def _identity(record: dict[str, Any]) -> tuple[Any, ...]:
        return (
            record["category"],
            record["chat_type"],
            record["player"],
            record.get("hero", ""),
            record["msg"],
        )

    def accept_frame(self, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if self.required_confirmations <= 1:
            return records

        unique_records: list[tuple[tuple[Any, ...], dict[str, Any]]] = []
        seen: set[tuple[Any, ...]] = set()
        for record in records:
            identity = self._identity(record)
            if identity in seen:
                continue
            seen.add(identity)
            unique_records.append((identity, record))

        emitted: list[dict[str, Any]] = []
        next_pending: dict[tuple[Any, ...], int] = {}
        next_committed: set[tuple[Any, ...]] = set()

        for identity, record in unique_records:
            if identity in self._committed_active:
                next_committed.add(identity)
                continue

            count = self._pending_counts.get(identity, 0) + 1
            if count >= self.required_confirmations:
                emitted.append(record)
                next_committed.add(identity)
            else:
                next_pending[identity] = count

        self._pending_counts = next_pending
        self._committed_active = next_committed
        return emitted


def capture():
    return np.array(pyautogui.screenshot(region=CONFIG["screen_region"]))


def default_metrics_log_name() -> str:
    timestamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    return f"performance_metrics_{timestamp}.csv"


def resolve_metrics_log_path(path_value: str | None) -> Path:
    paths = get_app_paths()
    if not path_value:
        return paths.log_dir / default_metrics_log_name()

    path = Path(path_value).expanduser()
    if path.is_absolute():
        return path
    return paths.log_dir / path


def create_metrics_collector(
    *,
    metrics_enabled_override: bool | None = None,
    metrics_interval_override: float | None = None,
    metrics_log_path_override: str | None = None,
    ocr_profile: ResolvedOCRProfile | None = None,
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
        screen_region=CONFIG["screen_region"],
        ocr_profile_name=ocr_profile.name if ocr_profile is not None else "",
        ocr_engine_id=ocr_profile.engine_id if ocr_profile is not None else "",
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
    cfg = resolve_ocr_profile(dict(CONFIG)).pipeline if config is None else config
    min_nonzero = max(int(cfg.get("min_mask_nonzero_pixels_for_ocr", 0)), 0)
    if min_nonzero == 0:
        return True
    return int(np.count_nonzero(mask)) >= min_nonzero


def _process_frame_for_live(
    screenshot: np.ndarray,
    ocr: OCRBackend,
    *,
    ocr_profile: ResolvedOCRProfile | None,
    metrics,
    started: float,
) -> dict[str, Any]:
    profile = resolve_ocr_profile(dict(CONFIG)) if ocr_profile is None else ocr_profile
    debug_kwargs: dict[str, Any] = {"should_run_ocr": should_run_ocr, "pre_cropped": True}
    if ocr_profile is not None:
        debug_kwargs["ocr_profile"] = profile
    debug_data = extract_chat_debug_data(screenshot, ocr, **debug_kwargs)
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
            ocr_profile_name=profile.name,
            ocr_engine_id=profile.engine_id,
        )
    return debug_data


def extract_chat_lines_for_live(
    screenshot: np.ndarray,
    ocr: OCRBackend,
    ocr_profile: ResolvedOCRProfile | None = None,
    metrics=None,
) -> dict[str, list[str]]:
    started = time.perf_counter()
    debug_data = _process_frame_for_live(
        screenshot,
        ocr,
        ocr_profile=ocr_profile,
        metrics=metrics,
        started=started,
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
    ocr_profile=None,
    team_buffer,
    all_buffer,
    chat_dedup,
    hero_dedup,
    chat_logger,
    hero_logger,
    metrics=None,
    reload_event: threading.Event | None = None,
    reload_notice: Queue | None = None,
) -> None:
    confirmation_gate = LiveRecordConfirmationGate(
        CONFIG.get("live_message_confirmations_required", 2)
    )
    allowed_charset = build_allowed_charset(CONFIG.get("languages") or [])

    try:
        while not stop_event.is_set() or not frame_queue.empty():
            try:
                if stop_event.is_set():
                    screenshot = frame_queue.get_nowait()
                else:
                    screenshot = frame_queue.get(timeout=0.1)
            except Empty:
                continue

            if reload_event is not None and reload_event.is_set():
                reload_event.clear()
                if ocr_profile is not None:
                    try:
                        new_profile = resolve_ocr_profile(dict(CONFIG))
                    except Exception as exc:
                        if reload_notice is not None:
                            reload_notice.put(("error", f"Config reload failed: {exc}"))
                    else:
                        # Engine or language changes would need the OCR backend
                        # rebuilt; that requires a full restart (Stop → Start).
                        # The GUI already warns about this in the save dialog.
                        if (
                            new_profile.engine_id == ocr_profile.engine_id
                            and list(new_profile.languages) == list(ocr_profile.languages)
                        ):
                            ocr_profile = new_profile

            started = time.perf_counter()
            debug_data = _process_frame_for_live(
                screenshot,
                ocr,
                ocr_profile=ocr_profile,
                metrics=metrics,
                started=started,
            )
            records = collect_normalized_records(
                debug_data["raw_lines"],
                team_buffer,
                all_buffer,
                line_ys_by_channel=debug_data.get("raw_line_ys"),
                raw_line_prefix_evidence_by_channel=debug_data.get("raw_line_prefix_evidence"),
                raw_continuation_y_gaps=debug_data.get("raw_continuation_y_gaps"),
            )
            if CONFIG.get("debug_snaps_on_anomaly"):
                try:
                    snap_dir = get_app_paths().snap_dir
                    if has_bboxes_without_lines(debug_data):
                        save_anomaly_snapshot(
                            debug_data,
                            snap_dir,
                            reason="bboxes_without_lines",
                            details={
                                "ocr_box_counts": {
                                    ch: len(debug_data["ocr_results"][ch])
                                    for ch in ("team", "all")
                                },
                            },
                        )
                    for record in records:
                        if contains_suspicious_characters(record, allowed_charset=allowed_charset):
                            save_anomaly_snapshot(
                                debug_data,
                                snap_dir,
                                reason="suspicious_chars",
                                details={
                                    "chat_type": record.get("chat_type"),
                                    "player": record.get("player"),
                                    "msg": record.get("msg"),
                                    "chars": suspicious_chars_in(record.get("msg", ""), allowed_charset),
                                },
                            )
                        embedded = message_contains_embedded_prefix(record)
                        if embedded is not None:
                            save_anomaly_snapshot(
                                debug_data,
                                snap_dir,
                                reason="embedded_prefix",
                                details={
                                    "chat_type": record.get("chat_type"),
                                    "player": record.get("player"),
                                    "msg": record.get("msg"),
                                    "match_span": list(embedded.span()),
                                    "matched_text": embedded.group(0),
                                },
                            )
                except Exception:
                    pass
            for record in confirmation_gate.accept_frame(records):
                log_normalized_record(
                    record,
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


def build_live_startup_banner(*, profile: ResolvedOCRProfile, paths) -> str:
    lines = [
        colorize_console_text(
            f"ChatOCR running with profile '{profile.name}' ({profile.engine_id}).",
            BANNER_HEADER_COLOR,
        ),
        "",
        colorize_console_text(f"Chat log:    {paths.chat_log}", BANNER_PATHS_COLOR),
        colorize_console_text(f"Hero log:    {paths.hero_log}", BANNER_PATHS_COLOR),
        colorize_console_text(f"Config file: {paths.config_path}", BANNER_SECONDARY_COLOR),
        colorize_console_text(f"Crash log:   {paths.crash_log}", BANNER_SECONDARY_COLOR),
        "",
        colorize_console_text("Live tracking active.", BANNER_READY_COLOR),
        colorize_console_text("Ctrl+C to stop.", BANNER_STOP_COLOR),
        "",
    ]
    return "\n".join(lines)


def run_live_logger(
    *,
    metrics_enabled_override: bool | None = None,
    metrics_interval_override: float | None = None,
    metrics_log_path_override: str | None = None,
    ocr_profile_override: str | None = None,
) -> int:
    # The CLI runner resolves the profile once and does not listen for config
    # reloads — there is no GUI Apply here. The GUI path (BackendBridge) wires a
    # reload_event into processing_worker so HSV/pipeline edits apply live.
    profile = resolve_ocr_profile(dict(CONFIG), ocr_profile_override)
    ocr = build_ocr_backend(profile)

    chat_dedup = DuplicateFilter(CONFIG["max_remembered"])
    hero_dedup = DuplicateFilter(CONFIG["max_remembered"])

    paths = get_app_paths()
    hero_logger = MessageLogger(
        str(paths.hero_log),
        print_messages=True,
        print_mode="hero",
        include_chat_type=False,
    )
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
        ocr_profile=profile,
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
            "ocr_profile": profile,
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

    print(build_live_startup_banner(profile=profile, paths=paths))

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
        processing_thread.join()
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
