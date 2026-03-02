import easyocr
import cv2
import time
import csv
import pyautogui
import numpy as np

# Setup
reader = easyocr.Reader(['en'])  # English
LOG_FILE = "chat_log.csv"

# Crop coords: adjust these! (x, y, width, height)
# Example: bottom-right chat box—test with print(pyautogui.position()) while hovering
CHAT_BOX = (1400, 800, 500, 300)  # tweak: x-start, y-start, w, h

def log_line(line):
    if "#" not in line:
        return
    # Split: "TiltLord#6969: ez noobs" → player + msg
    if ":" in line:
        player, msg = line.split(":", 1)
        player = player.strip()
        msg = msg.strip()
    else:
        player, msg = line.strip(), ""

    now = time.strftime("%Y-%m-%d %H:%M:%S")
    with open(LOG_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow( )

    print(f" {player}: {msg}")

print("Starting OCR loop... Press Ctrl+C to stop.")

while True:
    # Screenshot chat area only
    img = np.array(pyautogui.screenshot(region=CHAT_BOX))
    cv2.imwrite("chat_snap.png", img)  # optional debug

    # Read text
    result = reader.readtext(img, detail=0, paragraph=False)
    for line in result:
        if line.strip():  # skip blanks
            log_line(line)

    time.sleep(5)