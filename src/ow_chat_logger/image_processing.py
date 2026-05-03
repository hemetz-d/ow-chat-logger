from __future__ import annotations

from typing import Any, Mapping, Optional

import cv2
import numpy as np

from ow_chat_logger.config import CONFIG
from ow_chat_logger.parser import classify_line


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

    scale = _effective_scale_factor(cfg)
    upscaled = cv2.resize(
        mask,
        None,
        fx=scale,
        fy=scale,
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


def _bbox_center_y(bbox) -> float:
    ys = [point[1] for point in bbox]
    return (min(ys) + max(ys)) / 2.0


def _line_max_h(line) -> float:
    return (
        max((max(float(p[1]) for p in bbox) - min(float(p[1]) for p in bbox)) for bbox, _ in line)
        if line
        else 0.0
    )


def _line_center_y(line) -> float:
    return min(_bbox_center_y(bbox) for bbox, _ in line) if line else 0.0


def _line_top_y(line) -> float:
    return min(min(float(p[1]) for p in bbox) for bbox, _ in line) if line else 0.0


def _line_bottom_y(line) -> float:
    return max(max(float(p[1]) for p in bbox) for bbox, _ in line) if line else 0.0


def _line_first_box_x(line) -> float:
    return min(min(float(p[0]) for p in bbox) for bbox, _ in line) if line else 0.0


def _line_first_box_right_x(line) -> float:
    if not line:
        return 0.0
    first_bbox, _ = min(line, key=lambda item: min(float(p[0]) for p in item[0]))
    return max(float(p[0]) for p in first_bbox)


def _line_height(line) -> float:
    return _line_bottom_y(line) - _line_top_y(line) if line else 0.0


def _segment_dict(bbox, text: str) -> dict[str, float | str]:
    xs = [float(point[0]) for point in bbox]
    ys = [float(point[1]) for point in bbox]
    return {
        "text": text,
        "x1": min(xs),
        "x2": max(xs),
        "y1": min(ys),
        "y2": max(ys),
    }


def _reconstruct(
    results, config: Optional[Mapping[str, Any]] = None
) -> tuple[list[dict[str, float | str]], float]:
    """Core reconstruction.

    Returns ``(line_data, median_line_h)`` where ``line_data`` is a list of
    reconstructed line dictionaries sorted top-to-bottom and ``median_line_h``
    is the median bounding-box height across all reconstructed lines
    (0.0 when empty).
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
        segments = [_segment_dict(bbox, text) for bbox, text in line]
        result.append(
            {
                "text": " ".join(str(segment["text"]) for segment in segments),
                "center_y": y,
                "top_y": _line_top_y(line),
                "bottom_y": _line_bottom_y(line),
                "line_height": _line_height(line),
                "first_box_x": _line_first_box_x(line),
                "first_box_right_x": _line_first_box_right_x(line),
                "segments": segments,
            }
        )

    return result, median_line_h


def reconstruct_line_data(
    results, config: Optional[Mapping[str, Any]] = None
) -> tuple[list[dict[str, float | str]], float]:
    return _reconstruct(results, config)


def reconstruct_lines(results, config: Optional[Mapping[str, Any]] = None) -> list[str]:
    line_data, _ = _reconstruct(results, config)
    return [str(line["text"]) for line in line_data]


def reconstruct_lines_with_ys(
    results, config: Optional[Mapping[str, Any]] = None
) -> tuple[list[tuple[str, float]], float]:
    """Like reconstruct_lines but also returns each line's Y and the median line height."""
    line_data, median_line_h = _reconstruct(results, config)
    return [(str(line["text"]), float(line["center_y"])) for line in line_data], median_line_h


def compute_prefix_evidence_for_lines(
    mask: np.ndarray,
    line_data: list[dict[str, float | str]],
    median_line_h: float,
    config: Optional[Mapping[str, Any]] = None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    cfg = _cfg(config)
    min_anchor_lines = max(int(cfg.get("missing_prefix_min_anchor_lines", 2)), 1)
    body_start_tolerance = max(float(cfg.get("missing_prefix_body_start_tolerance", 20.0)), 0.0)
    right_padding = max(int(cfg.get("missing_prefix_span_right_padding", 8)), 0)
    vertical_padding = max(int(cfg.get("missing_prefix_vertical_padding", 8)), 0)
    min_nonzero = max(int(cfg.get("missing_prefix_min_span_nonzero_pixels", 1000)), 0)
    min_density = max(float(cfg.get("missing_prefix_min_span_density", 0.12)), 0.0)
    max_density = max(float(cfg.get("missing_prefix_max_span_density", 0.5)), min_density)
    max_largest_component_fraction = max(
        float(cfg.get("missing_prefix_max_largest_component_fraction", 0.8)),
        0.0,
    )
    min_line_height_fraction = max(
        float(cfg.get("missing_prefix_min_line_height_fraction", 0.65)), 0.0
    )
    max_line_height_fraction = max(
        float(cfg.get("missing_prefix_max_line_height_fraction", 1.6)),
        min_line_height_fraction,
    )

    def _extract_anchor(line: dict[str, Any]) -> dict[str, float] | None:
        classification = classify_line(str(line["text"]))
        if classification["category"] != "standard":
            return None

        segments = list(line.get("segments") or [])
        if len(segments) < 2:
            return None

        prefix_segments: list[dict[str, float | str]] = []
        saw_open = False
        saw_close = False
        body_segment = None

        for segment in segments:
            text = str(segment["text"])
            if not prefix_segments and "[" not in text:
                return None
            prefix_segments.append(segment)
            saw_open = saw_open or ("[" in text)
            saw_close = saw_close or ("]" in text)
            if saw_open and saw_close:
                break

        if not (saw_open and saw_close):
            return None

        for segment in segments[len(prefix_segments) :]:
            if any(char.isalnum() for char in str(segment["text"])):
                body_segment = segment
                break

        if body_segment is None:
            return None

        prefix_start_x = float(prefix_segments[0]["x1"])
        body_start_x = float(body_segment["x1"])
        return {
            "prefix_start_x": prefix_start_x,
            "body_start_x": body_start_x,
            "span_width": body_start_x - prefix_start_x,
        }

    anchors = [anchor for line in line_data if (anchor := _extract_anchor(line)) is not None]
    layout = {
        "anchor_count": len(anchors),
        "has_learned_layout": len(anchors) >= min_anchor_lines,
        "prefix_start_x": None,
        "body_start_range": None,
        "anchor_prefix_start_xs": [anchor["prefix_start_x"] for anchor in anchors],
        "anchor_body_start_xs": [anchor["body_start_x"] for anchor in anchors],
        "anchor_span_widths": [anchor["span_width"] for anchor in anchors],
    }
    if layout["has_learned_layout"]:
        prefix_start_x = float(np.median(layout["anchor_prefix_start_xs"]))
        body_start_min = min(layout["anchor_body_start_xs"]) - body_start_tolerance
        body_start_max = max(layout["anchor_body_start_xs"]) + body_start_tolerance
        layout["prefix_start_x"] = prefix_start_x
        layout["body_start_range"] = [body_start_min, body_start_max]

    evidence: list[dict[str, Any]] = []
    for line in line_data:
        classification = classify_line(str(line["text"]))
        first_box_x = float(line["first_box_x"])
        top_y = float(line["top_y"])
        bottom_y = float(line["bottom_y"])
        line_height = float(line.get("line_height", bottom_y - top_y))
        line_height_ratio = (line_height / median_line_h) if median_line_h > 0.0 else None
        within_line_height_range = (
            (
                line_height_ratio is not None
                and min_line_height_fraction <= line_height_ratio <= max_line_height_fraction
            )
            if median_line_h > 0.0
            else True
        )

        prefix_start_x = layout["prefix_start_x"]
        body_start_range = layout["body_start_range"]
        within_body_start_range = body_start_range is not None and float(
            body_start_range[0]
        ) <= first_box_x <= float(body_start_range[1])

        x1 = 0
        x2 = 0
        if prefix_start_x is not None:
            x1 = max(int(round(float(prefix_start_x))), 0)
            x2 = max(int(round(first_box_x)) - right_padding, x1)
        y1 = max(int(round(top_y)) - vertical_padding, 0)
        y2 = min(int(round(bottom_y)) + vertical_padding, mask.shape[0])

        probe_nonzero = 0
        probe_area = 0
        probe_density = 0.0
        probe_component_count = 0
        probe_largest_component_fraction = 0.0
        if x2 > x1 and y2 > y1:
            probe = mask[y1:y2, x1:x2]
            probe_nonzero = int(np.count_nonzero(probe))
            probe_area = int(probe.size)
            probe_density = (probe_nonzero / probe_area) if probe_area else 0.0
            if probe_nonzero > 0:
                _, _, stats, _ = cv2.connectedComponentsWithStats(
                    (probe > 0).astype(np.uint8),
                    8,
                )
                component_areas = [int(stats[i, cv2.CC_STAT_AREA]) for i in range(1, len(stats))]
                probe_component_count = len(component_areas)
                largest_area = max(component_areas) if component_areas else 0
                probe_largest_component_fraction = (
                    (largest_area / probe_nonzero) if probe_nonzero else 0.0
                )

        # With only one anchor, body_start_range is derived from a single sample and
        # cannot account for player-name length variance (a long anchor like [Power]:
        # produces a range that excludes a short missing prefix like [A7X]:). Trust
        # the probe density gate alone in that case — the stricter min_density floor
        # paired with anchor_count==1 already compensates.
        body_start_gate = within_body_start_range or layout["anchor_count"] == 1

        has_missing_prefix_evidence = (
            classification["category"] == "continuation"
            and bool(layout["has_learned_layout"])
            and body_start_gate
            and within_line_height_range
            and probe_nonzero >= min_nonzero
            and min_density <= probe_density <= max_density
            and probe_largest_component_fraction <= max_largest_component_fraction
        )

        evidence.append(
            {
                "anchor_count": layout["anchor_count"],
                "prefix_start_x": prefix_start_x,
                "body_start_range": body_start_range,
                "within_body_start_range": within_body_start_range,
                "probe_rect": [x1, y1, x2, y2],
                "probe_nonzero_pixels": probe_nonzero,
                "probe_area": probe_area,
                "probe_density": probe_density,
                "probe_component_count": probe_component_count,
                "probe_largest_component_fraction": probe_largest_component_fraction,
                "first_box_x": first_box_x,
                "first_box_right_x": float(line.get("first_box_right_x", first_box_x)),
                "top_y": top_y,
                "bottom_y": bottom_y,
                "line_height": line_height,
                "line_height_ratio": line_height_ratio,
                "within_line_height_range": within_line_height_range,
                "has_missing_prefix_evidence": has_missing_prefix_evidence,
            }
        )

    return layout, evidence
