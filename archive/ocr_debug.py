import os
import re
import csv
import time
import cv2
import easyocr
import numpy as np
import pyautogui
from collections import deque

# =========================
# Configuration
# =========================

LANGUAGES = ['en', 'de']
SCREEN_REGION = (50, 400, 500, 600)  # (left, top, width, height)
OCR_ALLOWLIST = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789# :[]*!?.,-üäöÜÄÖ+#()&%$§"='  # adjust based on expected characters
TEXT_THRESHOLD = 0.8
CAPTURE_INTERVAL = 2 # seconds
MAX_REMEMBERED_LINES = 2000

SNAP_DIR = "debug_snaps"
LOG_FILE = "chat_log.csv"


# =========================
# Initialization
# =========================

os.makedirs(SNAP_DIR, exist_ok=True)
reader = easyocr.Reader(LANGUAGES)

seen_lines = set()
seen_queue = deque(maxlen=MAX_REMEMBERED_LINES)

# =========================
# OCR + Image Processing
# =========================

def capture_screen():
    """Capture and preprocess chat area."""
    img = pyautogui.screenshot(region=SCREEN_REGION)
    img_np = np.array(img)
    return cv2.cvtColor(img_np, cv2.COLOR_BGR2GRAY)


def detect_chat(img_np):
    """Run OCR on image."""
    return reader.readtext(
        img_np,
        detail=0,
        paragraph=False, # TODO paragrah for longer messages and different matching
        allowlist=OCR_ALLOWLIST,
        text_threshold=TEXT_THRESHOLD
    )

# =========================
# Chat Parsing
# =========================

CHAT_PATTERN = re.compile(r'^\[(?P<player>[^\]]+)\]:\s*(?P<msg>.*)$')

def parse_line(line):
    line = line.strip()
    match = CHAT_PATTERN.match(line)

    if not match:
        return None

    return match.group("player").strip(), match.group("msg").strip()

# =========================
# Logging
# =========================

def log_line(line, timestamp):
    parsed = parse_line(line)
    if not parsed:
        return  # skip lines that don't match full pattern

    player, msg = parsed

    # if while typing
    if player in {"Team", "Match"}:
        return

    with open(LOG_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([timestamp, player, msg])

    print(f"{timestamp} | {player}: {msg}")


def is_new_line(line):
    """Duplicate filter to avoid logging the same line multiple times."""
    if line in seen_lines:
        return False

    if len(seen_queue) == seen_queue.maxlen:
        old = seen_queue.popleft()
        seen_lines.remove(old)

    seen_queue.append(line)
    seen_lines.add(line)
    return True


# =========================
# Main Modes
# =========================

def live_logger():
    print("Logging chat... Ctrl+C to stop.")
    i = 0

    while True:
        img = capture_screen()
        results = detect_chat(img)
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")

        for line in results:
            clean = line.strip()
            if clean and is_new_line(clean):
                log_line(clean, timestamp)

        i += 1
        time.sleep(CAPTURE_INTERVAL)


def live_debug():
    print("Live debug... Ctrl+C to stop.")
    i = 0

    while True:
        img = capture_screen()
        cv2.imwrite(f"{SNAP_DIR}/snap_{i}.png", img)
        print(f"Saved: snap_{i}.png")

        results = detect_chat(img)

        if results:
            print("OCR:")
            for line in results:
                print("  -", line)
        else:
            print("No text detected.")

        i += 1
        time.sleep(CAPTURE_INTERVAL)


# =========================
# Entry Point
# =========================

if __name__ == "__main__":
    live_logger()      # switch to live_debug() if needed