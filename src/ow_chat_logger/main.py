import datetime
import re
import time
import traceback

import numpy as np
import pyautogui

from ow_chat_logger.config import CONFIG, IGNORED_SENDERS, CHAT_LOG, HERO_LOG, CRASH_LOG
from ow_chat_logger.deduplication import DuplicateFilter
from ow_chat_logger.logger import MessageLogger
from ow_chat_logger.ocr_engine import OCREngine
from ow_chat_logger.pipeline import extract_chat_lines
from ow_chat_logger.buffer import MessageBuffer


def capture():
    return np.array(
        pyautogui.screenshot(region=CONFIG["screen_region"])
    )


def _write_crash_log(exc: BaseException) -> None:
    """Append a crash traceback to the configured crash log file."""

    # Ensure we always have an absolute path and that the directory exists.
    # The config module already creates the log folder, but we guard against
    # cases where the file might be deleted during runtime.
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
    if not finished:
        return

    player = re.sub(r"\s+", "", finished["player"].strip())
    msg = finished["msg"].strip()
    category = finished["category"]
    hero = finished.get("hero", "").strip()

    if player.lower() in IGNORED_SENDERS:
        return

    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")

    if category == "standard":
        if not msg or msg.isdigit():
            return
        key = f"{player}|{msg}"
        if chat_dedup.is_new(key):
            chat_logger.log(timestamp, player, msg, chat_type)

    elif category == "hero":
        if not hero:
            return
        hero_key = f"{player}|{hero}"
        if hero_dedup.is_new(hero_key):
            hero_logger.log(timestamp, player, hero, chat_type)


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

    print("ChatOCR running... Ctrl+C to stop.")

    try:
        try:
            while True:
                screenshot = capture()

                lines_by_channel = extract_chat_lines(screenshot, ocr)

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

                time.sleep(CONFIG["capture_interval"])

        except KeyboardInterrupt:
            print("\nStopping ChatOCR. Goodbye!\n")
        except Exception as exc:
            print("\nUnexpected error. Writing crash log and exiting.\n")
            _write_crash_log(exc)
    finally:
        _flush_buffers(
            team_buffer,
            all_buffer,
            chat_dedup=chat_dedup,
            hero_dedup=hero_dedup,
            chat_logger=chat_logger,
            hero_logger=hero_logger,
        )


if __name__ == "__main__":
    main()