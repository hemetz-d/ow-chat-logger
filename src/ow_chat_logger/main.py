import argparse
import datetime
import json
import re
import threading
import time
import traceback
from pathlib import Path
from queue import Empty, Full, Queue
from typing import Any, Sequence

import cv2
import numpy as np
import pyautogui

from ow_chat_logger.buffer import MessageBuffer
from ow_chat_logger.config import (
    CHAT_LOG,
    CONFIG,
    CRASH_LOG,
    HERO_LOG,
    IGNORED_SENDERS,
    LOG_DIR,
)
from ow_chat_logger.deduplication import DuplicateFilter
from ow_chat_logger.logger import MessageLogger
from ow_chat_logger.ocr_engine import OCREngine
from ow_chat_logger.pipeline import extract_chat_debug_data, extract_chat_lines

REPORT_SUFFIX_RE = re.compile(r"\s*\[\s*report\s*\]\s*$", re.IGNORECASE)
DISPLAY_CONFIG_KEYS = (
    "languages",
    "confidence_threshold",
    "text_threshold",
    "scale_factor",
    "y_merge_threshold",
    "team_hsv_lower",
    "team_hsv_upper",
    "all_hsv_lower",
    "all_hsv_upper",
    "use_gpu",
)


class LatestFrameQueue:
    """Bounded frame queue that always keeps the freshest screenshots."""

    def __init__(self, maxsize: int = 2):
        self._queue = Queue(maxsize=maxsize)

    def put_latest(self, item) -> None:
        while True:
            try:
                self._queue.put_nowait(item)
                return
            except Full:
                try:
                    self._queue.get_nowait()
                except Empty:
                    continue

    def get(self, timeout: float):
        return self._queue.get(timeout=timeout)

    def get_nowait(self):
        return self._queue.get_nowait()

    def empty(self) -> bool:
        return self._queue.empty()


def capture():
    return np.array(
        pyautogui.screenshot(region=CONFIG["screen_region"])
    )


def _write_crash_log(exc: BaseException) -> None:
    """Append a crash traceback to the configured crash log file."""

    from pathlib import Path

    crash_log_path = Path(CRASH_LOG)
    crash_log_path.parent.mkdir(parents=True, exist_ok=True)

    with crash_log_path.open("a", encoding="utf-8") as f:
        f.write("--- Crash on {} ---\n".format(datetime.datetime.now().isoformat()))
        f.write("".join(traceback.format_exception(type(exc), exc, exc.__traceback__)))
        f.write("\n")


def _process_finished(
    finished,
    chat_type,
    *,
    chat_dedup,
    hero_dedup,
    chat_logger,
    hero_logger,
):
    """Log one completed buffer message (standard chat or hero line)."""
    record = _normalize_finished_message(finished, chat_type)
    if not record:
        return

    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")

    if record["category"] == "standard":
        key = f"{record['player']}|{record['msg']}"
        if chat_dedup.is_new(key):
            chat_logger.log(timestamp, record["player"], record["msg"], chat_type)

    elif record["category"] == "hero":
        hero_key = f"{record['player']}|{record['hero']}"
        if hero_dedup.is_new(hero_key):
            hero_logger.log(timestamp, record["player"], record["hero"], chat_type)


def _normalize_finished_message(finished, chat_type):
    """Normalize one completed message and apply app-level filtering rules."""
    if not finished:
        return None

    player = re.sub(r"\s+", "", finished["player"].strip())
    msg = REPORT_SUFFIX_RE.sub("", finished["msg"]).strip()
    category = finished["category"]
    hero = finished.get("hero", "").strip()

    if player.lower() in IGNORED_SENDERS:
        return None

    if category == "standard":
        if not msg or msg.isdigit():
            return None
        return {
            "category": "standard",
            "chat_type": chat_type,
            "player": player,
            "msg": msg,
            "hero": "",
        }

    if category == "hero":
        if not hero:
            return None
        return {
            "category": "hero",
            "chat_type": chat_type,
            "player": player,
            "msg": msg,
            "hero": hero,
        }

    return None


def _flush_buffers(
    team_buffer,
    all_buffer,
    *,
    chat_dedup,
    hero_dedup,
    chat_logger,
    hero_logger,
):
    """Emit any messages still held in buffers (e.g. after Ctrl+C)."""
    _process_finished(
        team_buffer.flush(),
        "team",
        chat_dedup=chat_dedup,
        hero_dedup=hero_dedup,
        chat_logger=chat_logger,
        hero_logger=hero_logger,
    )
    _process_finished(
        all_buffer.flush(),
        "all",
        chat_dedup=chat_dedup,
        hero_dedup=hero_dedup,
        chat_logger=chat_logger,
        hero_logger=hero_logger,
    )


def _process_lines(
    lines_by_channel,
    team_buffer,
    all_buffer,
    *,
    chat_dedup,
    hero_dedup,
    chat_logger,
    hero_logger,
) -> None:
    """Process one screenshot's OCR lines as an isolated parsing session."""
    for chat_type in ("team", "all"):
        lines = lines_by_channel[chat_type]
        buffer = team_buffer if chat_type == "team" else all_buffer

        for line in lines:
            finished = buffer.feed(line)
            _process_finished(
                finished,
                chat_type,
                chat_dedup=chat_dedup,
                hero_dedup=hero_dedup,
                chat_logger=chat_logger,
                hero_logger=hero_logger,
            )

    _flush_buffers(
        team_buffer,
        all_buffer,
        chat_dedup=chat_dedup,
        hero_dedup=hero_dedup,
        chat_logger=chat_logger,
        hero_logger=hero_logger,
    )


def collect_screenshot_messages(lines_by_channel, *, include_hero_lines: bool = False):
    """Return filtered, per-screenshot parsed messages for regression-style checks."""
    out = {"team_lines": [], "all_lines": []}

    for chat_type in ("team", "all"):
        buffer = MessageBuffer()

        for line in lines_by_channel[chat_type]:
            finished = buffer.feed(line)
            record = _normalize_finished_message(finished, chat_type)
            if record:
                _append_collected_record(out, record, include_hero_lines=include_hero_lines)

        record = _normalize_finished_message(buffer.flush(), chat_type)
        if record:
            _append_collected_record(out, record, include_hero_lines=include_hero_lines)

    return out


def _append_collected_record(out, record, *, include_hero_lines: bool) -> None:
    if record["category"] == "standard":
        out[f"{record['chat_type']}_lines"].append(
            f"[{record['player']}]: {record['msg']}"
        )
    elif record["category"] == "hero" and include_hero_lines:
        if record["msg"]:
            out[f"{record['chat_type']}_lines"].append(
                f"{record['player']} ({record['hero']}): {record['msg']}"
            )
        else:
            out[f"{record['chat_type']}_lines"].append(
                f"{record['player']} ({record['hero']})"
            )


def _capture_worker(frame_queue, stop_event, error_queue) -> None:
    interval = max(float(CONFIG["capture_interval"]), 0.0)
    next_capture = time.monotonic()

    try:
        while not stop_event.is_set():
            now = time.monotonic()
            if now < next_capture and stop_event.wait(next_capture - now):
                break

            frame_queue.put_latest(capture())

            now = time.monotonic()
            if interval == 0:
                next_capture = now
            else:
                next_capture = max(next_capture + interval, now)
    except Exception as exc:
        error_queue.put(exc)
        stop_event.set()


def _processing_worker(
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

            lines_by_channel = extract_chat_lines(screenshot, ocr)
            _process_lines(
                lines_by_channel,
                team_buffer,
                all_buffer,
                chat_dedup=chat_dedup,
                hero_dedup=hero_dedup,
                chat_logger=chat_logger,
                hero_logger=hero_logger,
            )
    except Exception as exc:
        error_queue.put(exc)
        stop_event.set()


def _close_loggers(*loggers) -> None:
    for logger in loggers:
        logger.close()


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ow-chat-logger")
    subparsers = parser.add_subparsers(dest="command")

    analyze = subparsers.add_parser(
        "analyze",
        help="Run the OCR pipeline against a saved screenshot and emit debug artifacts.",
    )
    analyze.add_argument("--image", required=True, help="Path to the screenshot image.")
    analyze.add_argument(
        "--output-dir",
        help="Directory for generated debug artifacts. Defaults under the app debug folder.",
    )
    analyze.add_argument(
        "--config",
        help="Optional JSON config override file for this analysis run.",
    )
    return parser


def _load_json_file(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Expected JSON object in {path}")
    return data


def _load_rgb_image(path: Path) -> np.ndarray:
    bgr = cv2.imread(str(path))
    if bgr is None:
        raise FileNotFoundError(f"Could not read image: {path}")
    return cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)


def _default_analysis_output_dir() -> Path:
    timestamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    return Path(LOG_DIR) / "analysis" / timestamp


def _analysis_report_paths(output_dir: Path) -> dict[str, Path]:
    return {
        "original_image": output_dir / "original.png",
        "team_mask": output_dir / "team_mask.png",
        "all_mask": output_dir / "all_mask.png",
        "report": output_dir / "report.json",
    }


def _write_analysis_artifacts(
    analyzed_rgb_image: np.ndarray,
    debug_data: dict[str, Any],
    output_dir: Path,
) -> dict[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    paths = _analysis_report_paths(output_dir)

    cv2.imwrite(str(paths["original_image"]), cv2.cvtColor(analyzed_rgb_image, cv2.COLOR_RGB2BGR))
    cv2.imwrite(str(paths["team_mask"]), debug_data["masks"]["team"])
    cv2.imwrite(str(paths["all_mask"]), debug_data["masks"]["all"])

    return {key: str(path) for key, path in paths.items()}


def _print_analysis_summary(report: dict[str, Any], output_dir: Path) -> None:
    print(f"Analysis artifacts written to: {output_dir}")
    print("Effective OCR config:")
    for key in DISPLAY_CONFIG_KEYS:
        if key in report["effective_config"]:
            print(f"  {key}: {report['effective_config'][key]}")

    print("Final team lines:")
    if report["final_lines"]["team_lines"]:
        for line in report["final_lines"]["team_lines"]:
            print(f"  {line}")
    else:
        print("  <none>")

    print("Final all lines:")
    if report["final_lines"]["all_lines"]:
        for line in report["final_lines"]["all_lines"]:
            print(f"  {line}")
    else:
        print("  <none>")


def _run_analyze(args: argparse.Namespace) -> int:
    image_path = Path(args.image)
    output_dir = Path(args.output_dir) if args.output_dir else _default_analysis_output_dir()
    overrides = _load_json_file(Path(args.config)) if args.config else {}

    effective_config = {**CONFIG, **overrides}
    ocr = OCREngine(
        effective_config["languages"],
        effective_config["confidence_threshold"],
        effective_config["text_threshold"],
        use_gpu=effective_config.get("use_gpu", True),
    )

    rgb_image = _load_rgb_image(image_path)
    debug_data = extract_chat_debug_data(
        rgb_image,
        ocr,
        config_overrides=overrides,
    )
    final_lines = collect_screenshot_messages(debug_data["raw_lines"])
    report = {
        "source_image": str(image_path.resolve()),
        "effective_config": debug_data["config"],
        "raw_lines": debug_data["raw_lines"],
        "final_lines": final_lines,
    }
    report["artifacts"] = _write_analysis_artifacts(
        debug_data["cropped_rgb_image"],
        debug_data,
        output_dir,
    )
    Path(report["artifacts"]["report"]).write_text(json.dumps(report, indent=2), encoding="utf-8")
    _print_analysis_summary(report, output_dir)
    return 0


def run_live_logger() -> int:
    ocr = OCREngine(
        CONFIG["languages"],
        CONFIG["confidence_threshold"],
        CONFIG["text_threshold"],
        use_gpu=CONFIG.get("use_gpu", True),
    )

    chat_dedup = DuplicateFilter(CONFIG["max_remembered"])
    hero_dedup = DuplicateFilter(CONFIG["max_remembered"])

    hero_logger = MessageLogger(HERO_LOG)
    chat_logger = MessageLogger(CHAT_LOG, print_messages=True)

    team_buffer = MessageBuffer()
    all_buffer = MessageBuffer()
    frame_queue = LatestFrameQueue()
    stop_event = threading.Event()
    error_queue = Queue()

    capture_thread = threading.Thread(
        target=_capture_worker,
        args=(frame_queue, stop_event, error_queue),
        name="capture-worker",
        daemon=True,
    )
    processing_thread = threading.Thread(
        target=_processing_worker,
        args=(frame_queue, stop_event, error_queue),
        kwargs={
            "ocr": ocr,
            "team_buffer": team_buffer,
            "all_buffer": all_buffer,
            "chat_dedup": chat_dedup,
            "hero_dedup": hero_dedup,
            "chat_logger": chat_logger,
            "hero_logger": hero_logger,
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
            _write_crash_log(exc)
    finally:
        stop_event.set()
        capture_thread.join(timeout=1.0)
        processing_thread.join(timeout=1.0)
        _flush_buffers(
            team_buffer,
            all_buffer,
            chat_dedup=chat_dedup,
            hero_dedup=hero_dedup,
            chat_logger=chat_logger,
            hero_logger=hero_logger,
        )
        chat_logger.flush()
        hero_logger.flush()
        _close_loggers(chat_logger, hero_logger)
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if args.command == "analyze":
        return _run_analyze(args)
    return run_live_logger()


if __name__ == "__main__":
    raise SystemExit(main())
