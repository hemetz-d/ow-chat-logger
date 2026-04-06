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

def _bbox_center_y(bbox) -> float:
    ys = [point[1] for point in bbox]
    return (min(ys) + max(ys)) / 2.0


def _reconstruct(
    results, config: Optional[Mapping[str, Any]] = None
) -> tuple[list[tuple[str, float]], float]:
    """Core reconstruction.

    Returns ``(pairs, median_line_h)`` where ``pairs`` is a list of
    ``(text, center_y)`` sorted top-to-bottom and ``median_line_h`` is the
    median bounding-box height across all reconstructed lines (0.0 when empty).
    """
    cfg = _cfg(config)
    if not results:
        return [], 0.0

    results.sort(key=lambda x: _bbox_center_y(x[0]))

    lines = []
    current = []
    current_y = None

    for bbox, text, conf in results:
        y = _bbox_center_y(bbox)

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

    # Compute per-line max bounding-box height for filtering.
    def _line_max_h(line):
        return max(
            (max(float(p[1]) for p in bbox) - min(float(p[1]) for p in bbox))
            for bbox, _ in line
        ) if line else 0.0

    def _line_center_y(line):
        return min(_bbox_center_y(bbox) for bbox, _ in line)

    line_max_heights = [_line_max_h(line) for line in lines]
    line_ys = [_line_center_y(line) for line in lines]

    median_line_h = float(np.median(line_max_heights)) if line_max_heights else 0.0

    # Median-relative line height threshold: drop lines whose tallest box is
    # below (fraction × median line height).  A single-line result is never
    # filtered — its height trivially equals the median, so it always passes.
    fraction = float(cfg.get("min_box_height_fraction", 0.0))
    fraction_threshold = fraction * median_line_h if fraction > 0.0 else 0.0

    result = []
    for line, max_h, y in zip(lines, line_max_heights, line_ys):
        if fraction_threshold > 0.0 and max_h < fraction_threshold:
            continue
        line.sort(key=lambda x: x[0][0][0])
        result.append((" ".join(t for _, t in line), y))

    return result, median_line_h


def reconstruct_lines(results, config: Optional[Mapping[str, Any]] = None) -> list[str]:
    pairs, _ = _reconstruct(results, config)
    return [text for text, _ in pairs]


def reconstruct_lines_with_ys(
    results, config: Optional[Mapping[str, Any]] = None
) -> tuple[list[tuple[str, float]], float]:
    """Like reconstruct_lines but also returns each line's Y and the median line height."""
    return _reconstruct(results, config)
