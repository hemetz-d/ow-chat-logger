"""Shared OCR pipeline: screenshot RGB -> team / all chat line lists."""

from __future__ import annotations

import time
from typing import Any, Callable, Dict, Mapping, Optional

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
    should_run_ocr: Optional[Callable[[np.ndarray, Mapping[str, Any]], bool]] = None,
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

    preprocess_started = time.perf_counter()
    blue_mask, orange_mask = create_chat_masks(rgb_image, cfg)
    masks = {
        "team": clean_mask(blue_mask, cfg),
        "all": clean_mask(orange_mask, cfg),
    }
    preprocess_seconds = time.perf_counter() - preprocess_started

    ocr_started = time.perf_counter()
    ocr_results: dict[str, list[Any]] = {}
    ocr_skipped: dict[str, bool] = {}
    for key in ("team", "all"):
        mask = masks[key]
        should_run = True if should_run_ocr is None else should_run_ocr(mask, cfg)
        ocr_skipped[key] = not should_run
        ocr_results[key] = (
            ocr.run(
                mask,
                confidence_threshold=cfg["confidence_threshold"],
                text_threshold=cfg["text_threshold"],
            )
            if should_run
            else []
        )
    ocr_seconds = time.perf_counter() - ocr_started

    parse_started = time.perf_counter()
    out = {
        key: reconstruct_lines(ocr_results[key], cfg)
        for key in ("team", "all")
    }
    parse_seconds = time.perf_counter() - parse_started

    return {
        "config": cfg,
        "cropped_rgb_image": rgb_image,
        "masks": masks,
        "ocr_results": ocr_results,
        "ocr_skipped": ocr_skipped,
        "raw_lines": out,
        "timings": {
            "preprocess_seconds": preprocess_seconds,
            "ocr_seconds": ocr_seconds,
            "parse_seconds": parse_seconds,
        },
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
