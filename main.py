import time
import numpy as np
import pyautogui

from config import CONFIG, IGNORED_SENDERS, LOG_FILE
from deduplication import DuplicateFilter
from chat_logger import ChatLogger
from hero_logger import HeroLogger
from ocr_engine import OCREngine
from image_processing import (
    create_chat_masks,
    clean_mask,
    reconstruct_lines,
)
from buffer import MessageBuffer

def capture():
    return np.array(
        pyautogui.screenshot(region=CONFIG["screen_region"])
    )

def main():
    ocr = OCREngine(
        CONFIG["languages"],
        CONFIG["confidence_threshold"]
    )

    chat_dedup = DuplicateFilter(CONFIG["max_remembered"])
    hero_dedup = DuplicateFilter(CONFIG["max_remembered"])

    hero_logger = HeroLogger("hero_log.csv")
    chat_logger = ChatLogger(LOG_FILE)

    team_buffer = MessageBuffer()
    all_buffer = MessageBuffer()

    print("ChatOCR running... Ctrl+C to stop.")

    try:
        while True:
            screenshot = capture()

            blue_mask, orange_mask = create_chat_masks(screenshot)

            blue_mask = clean_mask(blue_mask)
            orange_mask = clean_mask(orange_mask)

            for mask, chat_type in [
                (blue_mask, "team"),
                (orange_mask, "all")
            ]:
                results = ocr.run(mask)
                lines = reconstruct_lines(results)

                buffer = team_buffer if chat_type == "team" else all_buffer

                for line in lines:
                    finished = buffer.feed(line)

                    if not finished:
                        continue

                    player = finished["player"].strip()
                    msg = finished["msg"].strip()
                    category = finished["category"]
                    hero = finished.get("hero", "").strip()

                    # Ignore unwanted senders globally
                    if player.lower() in IGNORED_SENDERS:
                        continue

                    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")

                    # ------------------------
                    # STANDARD CHAT MESSAGES
                    # ------------------------
                    if category == "standard":

                        if not msg or msg.isdigit():
                            continue

                        key = f"{player}|{msg}"

                        if chat_dedup.is_new(key):
                            chat_logger.log(timestamp, player, msg, chat_type)

                    # ------------------------
                    # HERO VOICELINES
                    # ------------------------
                    elif category == "hero":

                        if not hero:
                            continue

                        hero_key = f"{player}|{hero}"

                        if hero_dedup.is_new(hero_key):
                            hero_logger.log(timestamp, player, hero, chat_type)


            time.sleep(CONFIG["capture_interval"])

    except KeyboardInterrupt:
        print("\nCarcrashing ChatOCR with Headset. Goodbye!\n")


if __name__ == "__main__":
    main()