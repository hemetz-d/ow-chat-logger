from __future__ import annotations

from typing import Any, Mapping, Optional

import cv2
import numpy as np

from ow_chat_logger.config import CONFIG


def _cfg(config: Optional[Mapping[str, Any]]) -> Mapping[str, Any]:
    return CONFIG if config is None else config


def create_chat_masks(img_rgb, config: Optional[Mapping[str, Any]] = None):
    # pyautogui screenshots are RGB; OpenCV expects BGR by default.
    cfg = _cfg(config)
    hsv = cv2.cvtColor(img_rgb, cv2.COLOR_RGB2HSV)

    # BLUE (team)
    blue_lower = np.array(cfg["team_hsv_lower"], dtype=np.uint8)
    blue_upper = np.array(cfg["team_hsv_upper"], dtype=np.uint8)
    blue_mask = cv2.inRange(hsv, blue_lower, blue_upper)

    # ORANGE (all)
    orange_lower = np.array(cfg["all_hsv_lower"], dtype=np.uint8)
    orange_upper = np.array(cfg["all_hsv_upper"], dtype=np.uint8)
    orange_mask = cv2.inRange(hsv, orange_lower, orange_upper)

    return blue_mask, orange_mask


def remove_small_components(mask, min_area: int):
    if min_area <= 0:
        return mask

    num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(
        (mask > 0).astype(np.uint8),
        8,
    )
    cleaned = np.zeros_like(mask)
    for label in range(1, num_labels):
        area = int(stats[label, cv2.CC_STAT_AREA])
        if area >= min_area:
            cleaned[labels == label] = 255
    return cleaned


def _effective_scale_factor(cfg: Mapping[str, Any]) -> int | float:
    scale = cfg["scale_factor"]
    if cfg.get("high_quality_ocr", False):
        return max(scale, 3)
    return scale


def clean_mask_steps(
    mask,
    config: Optional[Mapping[str, Any]] = None,
) -> list[tuple[str, np.ndarray]]:
    cfg = _cfg(config)
    steps: list[tuple[str, np.ndarray]] = [("01_raw_threshold", mask.copy())]

    upscaled = cv2.resize(
        mask,
        None,
        fx=_effective_scale_factor(cfg),
        fy=_effective_scale_factor(cfg),
        interpolation=cv2.INTER_NEAREST,
    )
    steps.append(("02_upscaled", upscaled.copy()))

    current = upscaled
    if cfg.get("high_quality_ocr", False):
        closed = cv2.morphologyEx(current, cv2.MORPH_CLOSE, np.ones((2, 2), np.uint8))
        steps.append(("03_after_close", closed.copy()))
        opened = cv2.morphologyEx(closed, cv2.MORPH_OPEN, np.ones((2, 1), np.uint8))
        steps.append(("04_after_open", opened.copy()))
        current = opened

    cleaned = remove_small_components(current, int(cfg.get("min_component_area", 0)))
    if not np.array_equal(cleaned, current):
        steps.append(("05_after_component_filter", cleaned.copy()))

    return steps


def clean_mask(mask, config: Optional[Mapping[str, Any]] = None):
    return clean_mask_steps(mask, config)[-1][1]

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

def reconstruct_lines(results, config: Optional[Mapping[str, Any]] = None):
    cfg = _cfg(config)
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

        if abs(y - current_y) < cfg["y_merge_threshold"]:
            current.append((bbox, text))
            current_y = y
        else:
            lines.append(current)
            current = [(bbox, text)]
            current_y = y

    if current:
        lines.append(current)

    merged = []
    for line in lines:
        line.sort(key=lambda x: x[0][0][0])
        heights = []
        for bbox, _ in line:
            ys = [float(point[1]) for point in bbox]
            heights.append(max(ys) - min(ys))
        if heights and max(heights) < cfg.get("min_ocr_box_height", 60):
            continue
        merged.append(" ".join(t for _, t in line))

    return merged
