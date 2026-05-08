from __future__ import annotations

import re
import time
from typing import Any

from ow_chat_logger.buffer import MessageBuffer
from ow_chat_logger.config import IGNORED_SENDERS
from ow_chat_logger.hero_roster import canonicalize_hero_name

REPORT_SUFFIX_RE = re.compile(r"\s*\[\s*report\s*\]\s*$", re.IGNORECASE)

# T-48: chat interjections where a trailing `l` is almost certainly an OCR
# misread of `!`. Lowercased; matched against the last word of the body.
# Conservative whitelist — false negatives are accepted to avoid corrupting
# real English words ending in `l` (e.g. `cool`, `lol`, `kill`, `Daniel`).
_BODY_BANG_INTERJECTIONS = frozenset(
    {
        "epic",
        "you",  # appears in "thank you!"
        "nice",
        "good",
        "great",
        "awesome",
        "amazing",
        "wow",
        "sweet",
        "thanks",
        "ez",
        "wp",
        "gg",
        "noice",
        "sick",
        "insane",
        "cracked",
        "yo",
    }
)

_BODY_TRAILING_L_RE = re.compile(r"([A-Za-z]+)l\Z")
_BODY_TRAILING_I_AFTER_SPACE_RE = re.compile(r"\s+I\Z")


def _fix_body_trailing_punct(body: str) -> str:
    """Correct end-of-body OCR misreads of `!` (read as `l` or `I`).

    Two narrow rules, applied only to chat message bodies:
    1. body ends in ``<word>l`` where ``<word>`` is in the chat-interjection
       whitelist (`epic`, `you`, etc.) → rewrite trailing `l` as `!`.
    2. body ends in standalone capital `I` preceded by whitespace → rewrite
       to `!`. Risk: corrupts uncommon "...am I", "...was I" endings, but
       trailing-`I`-without-punctuation is rare in OW chat.
    """
    if not body or len(body) < 2:
        return body

    if _BODY_TRAILING_I_AFTER_SPACE_RE.search(body):
        return body[:-1] + "!"

    match = _BODY_TRAILING_L_RE.search(body)
    if match and match.group(1).lower() in _BODY_BANG_INTERJECTIONS:
        return body[:-1] + "!"

    return body


def normalize_finished_message(finished, chat_type):
    """Normalize one completed message and apply app-level filtering rules."""
    if not finished:
        return None

    player = re.sub(r"\s+", "", finished["player"].strip())
    msg = REPORT_SUFFIX_RE.sub("", finished["msg"]).strip()
    category = finished["category"]
    hero = finished.get("hero", "").strip()

    # OCR can read the fixed closing bracket in "[player]:" as a trailing "l" or "I".
    if (
        category == "standard"
        and finished.get("ocr_fix_closing_bracket")
        and player[-1:] in ("l", "I")
    ):
        player = player[:-1]

    if player.lower() in IGNORED_SENDERS:
        return None

    msg = _fix_body_trailing_punct(msg)

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
        hero = canonicalize_hero_name(hero)
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


def log_normalized_record(
    record,
    *,
    chat_dedup,
    hero_dedup,
    chat_logger,
    hero_logger,
    metrics=None,
) -> None:
    """Log one already-normalized record (standard chat or hero line)."""
    if not record:
        return

    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")

    if record["category"] == "standard":
        key = f"{record['player']}|{record['msg']}"
        if chat_dedup.is_new(key):
            chat_logger.log(timestamp, record["player"], record["msg"], record["chat_type"])
            if metrics is not None:
                metrics.record_logged_message("standard")

    elif record["category"] == "hero":
        hero_key = f"{record['player']}|{record['hero']}"
        if hero_dedup.is_new(hero_key):
            hero_logger.log(timestamp, record["player"], record["hero"], record["chat_type"])
            if metrics is not None:
                metrics.record_logged_message("hero")


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
    log_normalized_record(
        normalize_finished_message(finished, chat_type),
        chat_dedup=chat_dedup,
        hero_dedup=hero_dedup,
        chat_logger=chat_logger,
        hero_logger=hero_logger,
        metrics=metrics,
    )


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


def collect_normalized_records(
    lines_by_channel,
    team_buffer,
    all_buffer,
    *,
    line_ys_by_channel=None,
    raw_line_prefix_evidence_by_channel=None,
    raw_continuation_y_gaps=None,
) -> list[dict[str, Any]]:
    """Return normalized records extracted from one screenshot."""
    records: list[dict[str, Any]] = []

    for chat_type in ("team", "all"):
        lines = lines_by_channel[chat_type]
        buffer = team_buffer if chat_type == "team" else all_buffer
        ys = (line_ys_by_channel or {}).get(chat_type) or []
        prefix_evidence = (raw_line_prefix_evidence_by_channel or {}).get(chat_type) or []
        max_y_gap = (raw_continuation_y_gaps or {}).get(chat_type)

        for i, line in enumerate(lines):
            y = ys[i] if i < len(ys) else None
            evidence = prefix_evidence[i] if i < len(prefix_evidence) else None
            finished = buffer.feed(
                line,
                y,
                max_y_gap=max_y_gap,
                prefix_evidence=evidence,
            )
            record = normalize_finished_message(finished, chat_type)
            if record:
                records.append(record)

        record = normalize_finished_message(buffer.flush(), chat_type)
        if record:
            records.append(record)

    return records


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
    raw_line_prefix_evidence_by_channel=None,
    raw_continuation_y_gaps=None,
) -> None:
    """Process one screenshot's OCR lines as an isolated parsing session."""
    records = collect_normalized_records(
        lines_by_channel,
        team_buffer,
        all_buffer,
        line_ys_by_channel=line_ys_by_channel,
        raw_line_prefix_evidence_by_channel=raw_line_prefix_evidence_by_channel,
        raw_continuation_y_gaps=raw_continuation_y_gaps,
    )
    for record in records:
        log_normalized_record(
            record,
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
    raw_line_prefix_evidence_by_channel=None,
    raw_continuation_y_gaps=None,
) -> dict[str, list[str]]:
    """Return filtered, per-screenshot parsed messages for regression-style checks."""
    out = {"team_lines": [], "all_lines": []}
    records = collect_normalized_records(
        lines_by_channel,
        MessageBuffer(),
        MessageBuffer(),
        line_ys_by_channel=line_ys_by_channel,
        raw_line_prefix_evidence_by_channel=raw_line_prefix_evidence_by_channel,
        raw_continuation_y_gaps=raw_continuation_y_gaps,
    )
    for record in records:
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
        out[f"{record['chat_type']}_lines"].append(f"[{record['player']}]: {record['msg']}")
    elif record["category"] == "hero" and include_hero_lines:
        if record["msg"]:
            out[f"{record['chat_type']}_lines"].append(
                f"{record['player']} ({record['hero']}): {record['msg']}"
            )
        else:
            out[f"{record['chat_type']}_lines"].append(f"{record['player']} ({record['hero']})")
