import datetime
import re
import threading
import time
import traceback
from queue import Empty, Full, Queue

import numpy as np
import pyautogui

from ow_chat_logger.buffer import MessageBuffer
from ow_chat_logger.config import CONFIG, IGNORED_SENDERS, CHAT_LOG, HERO_LOG, CRASH_LOG
from ow_chat_logger.deduplication import DuplicateFilter
from ow_chat_logger.logger import MessageLogger
from ow_chat_logger.ocr_engine import OCREngine
from ow_chat_logger.pipeline import extract_chat_lines

REPORT_SUFFIX_RE = re.compile(r"\s*\[\s*report\s*\]\s*$", re.IGNORECASE)


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


def main():
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


if __name__ == "__main__":
    main()
