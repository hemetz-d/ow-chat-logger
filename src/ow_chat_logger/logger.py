import csv
from pathlib import Path


class MessageLogger:
    """Log chat/hero messages to a CSV file.

    This class is used for both chat messages and hero voicelines. Each row has
    the form [timestamp, player, text, chat_type].
    """

    def __init__(self, file_path: str, *, print_messages: bool = False):
        self.file_path = Path(file_path)
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        self.print_messages = print_messages

    def log(self, timestamp: str, player: str, text: str, chat_type: str):
        with self.file_path.open("a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([timestamp, player, text, chat_type])

        if self.print_messages:
            print(f"{timestamp} | {chat_type.upper()} | {player}: {text}")
