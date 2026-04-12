import csv
from pathlib import Path
from threading import Lock

ANSI_RESET = "\033[0m"
CHAT_TYPE_COLORS = {
    "team": "\033[38;5;117m",
    "all": "\033[38;5;214m",
}
HERO_TRACK_COLOR = "\033[38;5;77m"


def colorize_console_text(text: str, color: str | None) -> str:
    if not color:
        return text
    return f"{color}{text}{ANSI_RESET}"


class MessageLogger:
    """Log chat/hero messages to a CSV file.

    This class is used for both chat messages and hero voicelines. Each row has
    the form [timestamp, player, text, chat_type].
    """

    def __init__(
        self,
        file_path: str,
        *,
        print_messages: bool = False,
        print_mode: str = "chat",
    ):
        self.file_path = Path(file_path)
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        self.print_messages = print_messages
        self.print_mode = print_mode
        self._lock = Lock()
        self._file = self.file_path.open("a", newline="", encoding="utf-8")
        self._writer = csv.writer(self._file)
        self._closed = False

    def log(self, timestamp: str, player: str, text: str, chat_type: str):
        with self._lock:
            if self._closed:
                raise RuntimeError(f"Cannot log to closed file: {self.file_path}")
            self._writer.writerow([timestamp, player, text, chat_type])

        if self.print_messages:
            print(self._format_print_message(timestamp, player, text, chat_type))

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
        with self._lock:
            if self._closed:
                return
            self._file.flush()

    def close(self) -> None:
        with self._lock:
            if self._closed:
                return
            self._file.flush()
            self._file.close()
            self._closed = True
