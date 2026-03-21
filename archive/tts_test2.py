import win32com.client
import csv
import datetime
import time

LOG_FILE = "overwatch_chat.csv"

def log_message(text):
    if ":" in text:
        player, message = text.split(":", 1)
        player = player.strip()
        message = message.strip()
    else:
        player, message = "unknown", text.strip()

    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(LOG_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow( )

    print(f"Logged: {player} - {message}")

# Try to create voice and listen for events
try:
    voice = win32com.client.Dispatch("SAPI.SpVoice")
    print("Voice created.")
    # No sink—let's poll for active speech (not ideal, but test)
    while True:
        if voice.IsSpeaking():
            print("Speaking...")  # placeholder—need to grab text somehow
        time.sleep(0.5)
except Exception as e:
    print(f"Error: {e}")