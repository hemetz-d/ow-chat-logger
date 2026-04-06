from __future__ import annotations

import re
import time
from typing import Any

from ow_chat_logger.buffer import MessageBuffer
from ow_chat_logger.config import IGNORED_SENDERS

REPORT_SUFFIX_RE = re.compile(r"\s*\[\s*report\s*\]\s*$", re.IGNORECASE)


def normalize_finished_message(finished, chat_type):
    """Normalize one completed message and apply app-level filtering rules."""
    if not finished:
        return None

    player = re.sub(r"\s+", "", finished["player"].strip())
    msg = REPORT_SUFFIX_RE.sub("", finished["msg"]).strip()
    category = finished["category"]
    hero = finished.get("hero", "").strip()

    # OCR can read the fixed closing bracket in "[player]:" as a trailing "l" or "I".
    if category == "standard" and finished.get("ocr_fix_closing_bracket") and player[-1:] in ("l", "I"):
        player = player[:-1]

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


def process_finished(
    finished,
    chat_type,
    *,
    chat_dedup,
    hero_dedup,
    chat_logger,
    hero_logger,
    metrics=None,
) -> None:
    """Log one completed buffer message (standard chat or hero line)."""
    record = normalize_finished_message(finished, chat_type)
    if not record:
        return

    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")

    if record["category"] == "standard":
        key = f"{record['player']}|{record['msg']}"
        if chat_dedup.is_new(key):
            chat_logger.log(timestamp, record["player"], record["msg"], chat_type)
            if metrics is not None:
                metrics.record_logged_message("standard")

    elif record["category"] == "hero":
        hero_key = f"{record['player']}|{record['hero']}"
        if hero_dedup.is_new(hero_key):
            hero_logger.log(timestamp, record["player"], record["hero"], chat_type)
            if metrics is not None:
                metrics.record_logged_message("hero")


def flush_buffers(
    team_buffer,
    all_buffer,
    *,
    chat_dedup,
    hero_dedup,
    chat_logger,
    hero_logger,
    metrics=None,
) -> None:
    """Emit any messages still held in buffers (e.g. after Ctrl+C)."""
    process_finished(
        team_buffer.flush(),
        "team",
        chat_dedup=chat_dedup,
        hero_dedup=hero_dedup,
        chat_logger=chat_logger,
        hero_logger=hero_logger,
        metrics=metrics,
    )
    process_finished(
        all_buffer.flush(),
        "all",
        chat_dedup=chat_dedup,
        hero_dedup=hero_dedup,
        chat_logger=chat_logger,
        hero_logger=hero_logger,
        metrics=metrics,
    )


def process_lines(
    lines_by_channel,
    team_buffer,
    all_buffer,
    *,
    chat_dedup,
    hero_dedup,
    chat_logger,
    hero_logger,
    metrics=None,
    line_ys_by_channel=None,
    raw_continuation_y_gaps=None,
) -> None:
    """Process one screenshot's OCR lines as an isolated parsing session."""
    for chat_type in ("team", "all"):
        lines = lines_by_channel[chat_type]
        buffer = team_buffer if chat_type == "team" else all_buffer
        ys = (line_ys_by_channel or {}).get(chat_type) or []
        max_y_gap = (raw_continuation_y_gaps or {}).get(chat_type)

        for i, line in enumerate(lines):
            y = ys[i] if i < len(ys) else None
            finished = buffer.feed(line, y, max_y_gap=max_y_gap)
            process_finished(
                finished,
                chat_type,
                chat_dedup=chat_dedup,
                hero_dedup=hero_dedup,
                chat_logger=chat_logger,
                hero_logger=hero_logger,
                metrics=metrics,
            )

    flush_buffers(
        team_buffer,
        all_buffer,
        chat_dedup=chat_dedup,
        hero_dedup=hero_dedup,
        chat_logger=chat_logger,
        hero_logger=hero_logger,
        metrics=metrics,
    )


def collect_screenshot_messages(
    lines_by_channel,
    *,
    include_hero_lines: bool = False,
    line_ys_by_channel=None,
    raw_continuation_y_gaps=None,
) -> dict[str, list[str]]:
    """Return filtered, per-screenshot parsed messages for regression-style checks."""
    out = {"team_lines": [], "all_lines": []}

    for chat_type in ("team", "all"):
        buffer = MessageBuffer()
        ys = (line_ys_by_channel or {}).get(chat_type) or []
        max_y_gap = (raw_continuation_y_gaps or {}).get(chat_type)

        for i, line in enumerate(lines_by_channel[chat_type]):
            y = ys[i] if i < len(ys) else None
            finished = buffer.feed(line, y, max_y_gap=max_y_gap)
            record = normalize_finished_message(finished, chat_type)
            if record:
                append_collected_record(
                    out,
                    record,
                    include_hero_lines=include_hero_lines,
                )

        record = normalize_finished_message(buffer.flush(), chat_type)
        if record:
            append_collected_record(
                out,
                record,
                include_hero_lines=include_hero_lines,
            )

    return out


def append_collected_record(
    out: dict[str, list[str]],
    record: dict[str, Any],
    *,
    include_hero_lines: bool,
) -> None:
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
