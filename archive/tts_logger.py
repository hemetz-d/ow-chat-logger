import pyttsx3
import csv
import datetime
import sys

# Open (or create) log file
LOG_FILE = "overwatch_chat.csv"

def log_message(text):
    # Guess player + message (crude but works)
    if ":" in text:
        player, message = text.split(":", 1)
        player = player.strip()
        message = message.strip()
    else:
        player, message = "unknown", text.strip()

    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    row = [now, player, message]

    with open(LOG_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(row)

    print(f"Logged: {player} - {message}")  # debug

# Main TTS loop
engine = pyttsx3.init()
engine.setProperty('voice', engine.getProperty('voices')[0].id)  # default voice

def on_speak(text):
    log_message(text)          # save it first
    engine.say(text)           # then speak normally
    engine.runAndWait()

# This is what Balabolka will call
if __name__ == "__main__":
    if len(sys.argv) > 1:
        text = " ".join(sys.argv[1:])
        on_speak(text)
    else:
        print("Waiting for TTS calls...")
        while True:
            pass  # keeps script alive