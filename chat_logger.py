import csv

class ChatLogger:
    def __init__(self, logfile):
        self.logfile = logfile

    def log(self, timestamp, player, msg, chat_type):
        with open(self.logfile, "a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([timestamp, player, msg, chat_type])

        print(f"{timestamp} | {chat_type.upper()} | {player}: {msg}")