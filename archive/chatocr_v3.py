import os
import re
import csv
import time
import cv2
import easyocr
import numpy as np
import pyautogui
import shutil
from collections import deque

# =========================
# CONFIG
# =========================

CONFIG = {
    "languages": ['en', 'de'],
    "screen_region": (50, 400, 500, 600),
    "scale_factor": 3,
    "y_merge_threshold": 18,
    "confidence_threshold": 0.4,
    "capture_interval": 1.0,
    "max_remembered": 2000,
}

IGNORED_SENDERS = {"team", "match"}
DEBUG_LEVEL = 2  # 0=off, 1=lines, 2=masks, 3=boxes

LOG_FILE = "chat_log.csv"
SNAP_DIR = "debug_snaps"

os.makedirs(SNAP_DIR, exist_ok=True)
if os.path.exists(SNAP_DIR):
    shutil.rmtree(SNAP_DIR)          # delete whole folder
os.makedirs(SNAP_DIR, exist_ok=True) # recreate empty

reader = easyocr.Reader(CONFIG["languages"])

seen_lines = set()
seen_queue = deque(maxlen=CONFIG["max_remembered"])


# =========================
# COLOR MASKING
# =========================

def create_chat_masks(img_bgr):
    hsv = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)

    # BLUE (team)
    blue_lower = np.array([85, 150, 150])
    blue_upper = np.array([110, 255, 255])
    blue_mask = cv2.inRange(hsv, blue_lower, blue_upper)

    # ORANGE (all)
    orange_lower = np.array([2, 120, 150])
    orange_upper = np.array([25, 255, 255])
    orange_mask = cv2.inRange(hsv, orange_lower, orange_upper)

    return blue_mask, orange_mask


def clean_mask(mask):
    # First upscale
    mask = cv2.resize(
        mask,
        None,
        fx=CONFIG["scale_factor"],
        fy=CONFIG["scale_factor"],
        interpolation=cv2.INTER_NEAREST
    )

    # Then apply very light horizontal close
    kernel = np.ones((1, 2), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)

    return mask

# def clean_mask(mask):
#     mask = cv2.resize(
#         mask,
#         None,
#         fx=3,
#         fy=3,
#         interpolation=cv2.INTER_NEAREST
#     )
#     return mask

# =========================
# OCR
# =========================

def run_ocr(mask):
    results = reader.readtext(
        mask,
        detail=1,
        paragraph=False,
        text_threshold=0.4,
        allowlist='abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789# :[]*!?.,-üäöÜÄÖ+#()&%$§"='
    )

    return [
        (bbox, text, conf)
        for (bbox, text, conf) in results
        if conf > CONFIG["confidence_threshold"]
    ]


# =========================
# LINE RECONSTRUCTION
# =========================

def reconstruct_lines(results):
    if not results:
        return []

    results.sort(key=lambda x: x[0][0][1])

    lines = []
    current = []
    current_y = None

    for bbox, text, conf in results:
        y = bbox[0][1]

        if current_y is None:
            current_y = y

        if abs(y - current_y) < CONFIG["y_merge_threshold"]:
            current.append((bbox, text))
        else:
            lines.append(current)
            current = [(bbox, text)]
            current_y = y

    if current:
        lines.append(current)

    merged = []
    for line in lines:
        line.sort(key=lambda x: x[0][0][0])
        merged.append(" ".join(t for _, t in line))

    return merged


# =========================
# PARSING
# =========================

STANDARD_PATTERN = re.compile(
    r'^\[(?P<player>[^\]]+)\]:\s*(?P<msg>.*)$'
)

HERO_PATTERN = re.compile(
    r'^(?P<player>[^()]+)\s+\((?P<hero>[^)]+)\):\s*(?P<msg>.*)$'
)


def classify_line(line):
    line = normalize(line)

    # fix OCR colon issue
    line = line.replace(";", ":")

    m1 = STANDARD_PATTERN.match(line)
    if m1:
        return {
            "category": "standard",
            "player": m1.group("player").strip(),
            "hero": "",
            "msg": m1.group("msg").strip()
        }

    m2 = HERO_PATTERN.match(line)
    if m2:
        return {
            "category": "hero",
            "player": m2.group("player").strip(),
            "hero": m2.group("hero").strip(),
            "msg": m2.group("msg").strip()
        }

    return None  # continuation


# =========================
# DUPLICATE FILTER
# =========================

def normalize(text):
    return re.sub(r'\s+', ' ', text.strip())


def is_new_line(line):
    line = normalize(line)

    if line in seen_lines:
        return False

    if len(seen_queue) == seen_queue.maxlen:
        old = seen_queue.popleft()
        seen_lines.remove(old)

    seen_queue.append(line)
    seen_lines.add(line)
    return True


# =========================
# LOGGING
# =========================

def log_line(timestamp, player, msg, chat_type):
    with open(LOG_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([timestamp, player, msg, chat_type])

    print(f"{timestamp} | {chat_type.upper()} | {player}: {msg}")


class MessageBuffer:
    def __init__(self):
        self.current = None

    def feed(self, line, chat_type):
        classification = classify_line(line)

        # New message start
        if classification is not None:
            finished = self.current
            self.current = {
                "player": classification["player"],
                "hero": classification["hero"],
                "msg": classification["msg"],
                "chat_type": chat_type,
                "category": classification["category"]
            }
            return finished

        # Continuation
        if self.current:
            self.current["msg"] += " " + line.strip()

        return None

    def flush(self):
        finished = self.current
        self.current = None
        return finished


# =========================
# MAIN LOOP
# =========================

def live_logger():
    print("ChatOCR v3 running... Ctrl+C to stop.")
    iteration = 0
    team_buffer = MessageBuffer()
    all_buffer = MessageBuffer()

    while True:
        screenshot = np.array(
            pyautogui.screenshot(region=CONFIG["screen_region"])
        )

        blue_mask, orange_mask = create_chat_masks(screenshot)

        blue_mask = clean_mask(blue_mask)
        orange_mask = clean_mask(orange_mask)

        if DEBUG_LEVEL >= 2:
            cv2.imwrite(f"{SNAP_DIR}/{iteration}_blue.png", blue_mask)
            cv2.imwrite(f"{SNAP_DIR}/{iteration}_orange.png", orange_mask)

        iteration += 1

        for mask, chat_type in [(blue_mask, "team"), (orange_mask, "all")]:

            results = run_ocr(mask)
            lines = reconstruct_lines(results)

            if DEBUG_LEVEL >= 1:
                print(f"\n[{chat_type.upper()} DETECTED LINES]")
                for l in lines:
                    print("  ", l)

            buffer = team_buffer if chat_type == "team" else all_buffer

            # ---- FEED LINES ----
            for line in lines:
                finished_message = buffer.feed(line, chat_type)

                if finished_message:
                    full_text = finished_message["msg"]

                    player = finished_message["player"].strip()
                    full_text = finished_message["msg"].strip()

                    # Ignore unwanted senders
                    if player.lower() in IGNORED_SENDERS:
                        continue

                    # Ignore empty or numeric garbage
                    if not full_text or full_text.isdigit():
                        continue

                    if is_new_line(full_text):
                        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
                        log_line(
                            timestamp,
                            player,
                            full_text,
                            finished_message["chat_type"]
                        )

        time.sleep(CONFIG["capture_interval"])


# =========================

if __name__ == "__main__":
    live_logger()