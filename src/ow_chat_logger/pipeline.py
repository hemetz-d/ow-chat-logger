"""Shared OCR pipeline: screenshot RGB -> team / all chat line lists.

Used by regression tests and optional tooling; mirrors ``main`` loop logic.
"""

from __future__ import annotations

from typing import Any, Dict, Mapping, Optional

import numpy as np

from ow_chat_logger.config import CONFIG
from ow_chat_logger.image_processing import (
    clean_mask,
    create_chat_masks,
    reconstruct_lines,
)
from ow_chat_logger.ocr_engine import OCREngine


def merge_pipeline_config(overrides: Optional[Mapping[str, Any]] = None) -> Dict[str, Any]:
    """Merge runtime CONFIG with optional overrides (e.g. per-sample regression)."""
    if not overrides:
        return dict(CONFIG)
    return {**CONFIG, **dict(overrides)}


def crop_to_screen_region(
    rgb_image: np.ndarray,
    config_overrides: Optional[Mapping[str, Any]] = None,
) -> np.ndarray:
    """Crop full-screen images to the configured capture region when possible.

    Live runtime already captures only ``screen_region``. Regression/analyze inputs
    may be full-screen screenshots, so crop them first when the region fits.
    """
    cfg = merge_pipeline_config(config_overrides)
    region = cfg.get("screen_region")
    if not region or len(region) != 4:
        return rgb_image

    left, top, width, height = [int(v) for v in region]
    if left < 0 or top < 0 or width <= 0 or height <= 0:
        return rgb_image

    image_height, image_width = rgb_image.shape[:2]
    right = left + width
    bottom = top + height

    if right > image_width or bottom > image_height:
        return rgb_image

    return rgb_image[top:bottom, left:right]


def extract_chat_debug_data(
    rgb_image: np.ndarray,
    ocr: OCREngine,
    *,
    config_overrides: Optional[Mapping[str, Any]] = None,
) -> dict[str, Any]:
    """Run masks + OCR + reconstruction and return intermediate debug data.

    Parameters
    ----------
    rgb_image
        HxWx3 uint8 RGB (same as ``pyautogui.screenshot`` after ``np.array``).
    ocr
        Initialized :class:`OCREngine` (can be CPU/GPU).
    config_overrides
        Partial config dict (e.g. ``scale_factor``, ``confidence_threshold``).
    """
    cfg = merge_pipeline_config(config_overrides)
    rgb_image = crop_to_screen_region(rgb_image, config_overrides)

    blue_mask, orange_mask = create_chat_masks(rgb_image, cfg)
    out: dict[str, list[str]] = {}
    masks: dict[str, np.ndarray] = {}

    for mask, key in [
        (clean_mask(blue_mask, cfg), "team"),
        (clean_mask(orange_mask, cfg), "all"),
    ]:
        masks[key] = mask
        results = ocr.run(mask)
        out[key] = reconstruct_lines(results, cfg)

    return {
        "config": cfg,
        "cropped_rgb_image": rgb_image,
        "masks": masks,
        "raw_lines": out,
    }


def extract_chat_lines(
    rgb_image: np.ndarray,
    ocr: OCREngine,
    *,
    config_overrides: Optional[Mapping[str, Any]] = None,
) -> dict[str, list[str]]:
    """Run masks + OCR + line reconstruction for team and all chat."""
    return extract_chat_debug_data(
        rgb_image,
        ocr,
        config_overrides=config_overrides,
    )["raw_lines"]
