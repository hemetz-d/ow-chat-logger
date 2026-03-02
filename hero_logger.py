import csv

class HeroLogger:
    def __init__(self, file_path):
        self.file_path = file_path

    def log(self, timestamp, player, hero, chat_type):
        with open(self.file_path, "a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([timestamp, player, hero, chat_type])