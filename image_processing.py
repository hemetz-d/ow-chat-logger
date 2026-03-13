import cv2
import numpy as np

from config import CONFIG

def create_chat_masks(img_rgb):
    # pyautogui screenshots are RGB; OpenCV expects BGR by default.
    hsv = cv2.cvtColor(img_rgb, cv2.COLOR_RGB2HSV)

    # BLUE (team)
    blue_lower = np.array(CONFIG["team_hsv_lower"], dtype=np.uint8)
    blue_upper = np.array(CONFIG["team_hsv_upper"], dtype=np.uint8)
    blue_mask = cv2.inRange(hsv, blue_lower, blue_upper)

    # ORANGE (all)
    orange_lower = np.array(CONFIG["all_hsv_lower"], dtype=np.uint8)
    orange_upper = np.array(CONFIG["all_hsv_upper"], dtype=np.uint8)
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

# option with less processing (just upscaling)
# def clean_mask(mask):
#     mask = cv2.resize(
#         mask,
#         None,
#         fx=3,
#         fy=3,
#         interpolation=cv2.INTER_NEAREST
#     )
#     return mask

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