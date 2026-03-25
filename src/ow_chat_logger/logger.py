import csv
from pathlib import Path
from threading import Lock


class MessageLogger:
    """Log chat/hero messages to a CSV file.

    This class is used for both chat messages and hero voicelines. Each row has
    the form [timestamp, player, text, chat_type].
    """

    def __init__(self, file_path: str, *, print_messages: bool = False):
        self.file_path = Path(file_path)
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        self.print_messages = print_messages
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
            print(f"{timestamp} | {chat_type.upper()} | {player}: {text}")

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
