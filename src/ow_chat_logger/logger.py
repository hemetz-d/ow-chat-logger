"""Persist chat and hero records to the canonical SQLite store.

``MessageLogger`` is the single entry point that the live runtime uses to
record both regular chat messages and hero-pick events. Two instances run
in parallel today (``include_chat_type=True`` for chat, ``False`` for
hero); both now write to the same database via different ``source`` values
on the shared ``messages`` table.

The public ``log()`` / ``flush()`` / ``close()`` shape and the colorized
print path are unchanged so existing callers and the 6 logger tests stay
on the same contract.
"""

from __future__ import annotations

from pathlib import Path
from threading import Lock

from ow_chat_logger._chat_db import open_db

ANSI_RESET = "\033[0m"
CHAT_TYPE_COLORS = {
    "team": "\033[38;5;117m",
    "all": "\033[38;5;214m",
}
HERO_TRACK_COLOR = "\033[38;5;77m"

_VALID_SOURCES = frozenset({"team", "all", "hero"})


def colorize_console_text(text: str, color: str | None) -> str:
    if not color:
        return text
    return f"{color}{text}{ANSI_RESET}"


class MessageLogger:
    """Append chat or hero records into the canonical SQLite store."""

    def __init__(
        self,
        file_path: str,
        *,
        print_messages: bool = False,
        print_mode: str = "chat",
        include_chat_type: bool = True,
    ):
        # ``file_path`` historically named the CSV; it now names the SQLite
        # DB. The argument keeps its old name so live_runtime / tests don't
        # need a signature change. Both the chat and hero loggers point at
        # the same DB; rows are discriminated by ``source``.
        self.file_path = Path(file_path)
        self.print_messages = print_messages
        self.print_mode = print_mode
        # ``include_chat_type=True`` means this logger expects the caller to
        # supply ``chat_type`` per row (the chat logger). ``False`` means
        # this logger always writes ``source='hero'`` (the hero logger).
        self.include_chat_type = include_chat_type
        self._lock = Lock()
        self._conn = open_db(self.file_path)
        self._closed = False

    def log(
        self,
        timestamp: str,
        player: str,
        text: str,
        chat_type: str | None = None,
    ):
        with self._lock:
            if self._closed:
                raise RuntimeError(f"Cannot log to closed file: {self.file_path}")
            if self.include_chat_type:
                if chat_type is None:
                    raise ValueError("chat_type is required for chat log rows")
                source = chat_type.strip().lower()
                if source not in _VALID_SOURCES or source == "hero":
                    # Chat logger may only emit team/all. Reject "hero" too —
                    # those go through the dedicated hero logger.
                    raise ValueError(f"chat_type must be 'team' or 'all' (got {chat_type!r})")
            else:
                source = "hero"
            self._conn.execute(
                "INSERT INTO messages "
                "(timestamp, player, player_lc, text, text_lc, source) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (timestamp, player, player.lower(), text, text.lower(), source),
            )
            self._conn.commit()

        if self.print_messages:
            print(self._format_print_message(timestamp, player, text, chat_type or ""))

    def _format_print_message(
        self,
        timestamp: str,
        player: str,
        text: str,
        chat_type: str,
    ) -> str:
        if self.print_mode == "hero":
            return colorize_console_text(
                f"{timestamp} | {'HERO':<4} | {player} / {text}",
                HERO_TRACK_COLOR,
            )

        return colorize_console_text(
            f"{timestamp} | {chat_type.upper():<4} | {player}: {text}",
            CHAT_TYPE_COLORS.get(chat_type.lower()),
        )

    def flush(self) -> None:
        # Each ``log()`` already commits; ``flush`` is a no-op kept for
        # backward compatibility with callers that drained the CSV writer.
        with self._lock:
            if self._closed:
                return

    def close(self) -> None:
        with self._lock:
            if self._closed:
                return
            self._conn.close()
            self._closed = True
