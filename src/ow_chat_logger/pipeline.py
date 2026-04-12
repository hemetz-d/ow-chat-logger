"""Shared OCR pipeline: screenshot RGB -> team / all chat line lists."""

from __future__ import annotations

import time
from typing import Any, Callable, Dict, Mapping, Optional

import numpy as np

from ow_chat_logger.config import CONFIG, resolve_ocr_profile
from ow_chat_logger.image_processing import (
    clean_mask_steps,
    compute_prefix_evidence_for_lines,
    create_chat_masks,
    reconstruct_line_data,
)
from ow_chat_logger.ocr import OCRBackend, ResolvedOCRProfile


def merge_pipeline_config(overrides: Optional[Mapping[str, Any]] = None) -> Dict[str, Any]:
    """Merge runtime CONFIG with optional overrides (e.g. per-sample regression)."""
    return merge_pipeline_config_for_profile(
        profile=resolve_ocr_profile(dict(CONFIG)),
        overrides=overrides,
    )


def merge_pipeline_config_for_profile(
    *,
    profile: ResolvedOCRProfile,
    overrides: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    cfg = {
        **profile.pipeline,
        "languages": list(profile.languages),
        "ocr_profile": profile.name,
        "ocr_engine": profile.engine_id,
    }
    if overrides:
        cfg.update(dict(overrides))
    return cfg


def crop_to_screen_region(
    rgb_image: np.ndarray,
    config_overrides: Optional[Mapping[str, Any]] = None,
    *,
    profile: ResolvedOCRProfile | None = None,
) -> np.ndarray:
    """Crop full-screen images to the configured capture region when possible.

    Live runtime already captures only ``screen_region``. Regression/analyze inputs
    may be full-screen screenshots, so crop them first when the region fits.
    """
    active_profile = resolve_ocr_profile(dict(CONFIG)) if profile is None else profile
    cfg = merge_pipeline_config_for_profile(profile=active_profile, overrides=config_overrides)
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
    ocr: OCRBackend,
    *,
    config_overrides: Optional[Mapping[str, Any]] = None,
    should_run_ocr: Optional[Callable[[np.ndarray, Mapping[str, Any]], bool]] = None,
    ocr_profile: ResolvedOCRProfile | None = None,
    pre_cropped: bool = False,
) -> dict[str, Any]:
    """Run masks + OCR + reconstruction and return intermediate debug data.

    Parameters
    ----------
    rgb_image
        HxWx3 uint8 RGB (same as ``pyautogui.screenshot`` after ``np.array``).
    ocr
        Initialized :class:`OCREngine`.
    config_overrides
        Partial config dict (e.g. ``scale_factor``, ``screen_region``).
    pre_cropped
        Set ``True`` when the caller has already cropped to ``screen_region``
        (e.g. live capture via ``pyautogui.screenshot(region=...)``).  Skips
        the ``crop_to_screen_region`` call entirely.
    """
    profile = resolve_ocr_profile(dict(CONFIG)) if ocr_profile is None else ocr_profile
    cfg = merge_pipeline_config_for_profile(profile=profile, overrides=config_overrides)
    if not pre_cropped:
        rgb_image = crop_to_screen_region(rgb_image, config_overrides, profile=profile)

    preprocess_started = time.perf_counter()
    blue_mask, orange_mask = create_chat_masks(rgb_image, cfg)
    mask_debug_steps = {
        "team": clean_mask_steps(blue_mask, cfg),
        "all": clean_mask_steps(orange_mask, cfg),
    }
    masks = {
        "team": mask_debug_steps["team"][-1][1],
        "all": mask_debug_steps["all"][-1][1],
    }
    preprocess_seconds = time.perf_counter() - preprocess_started

    ocr_started = time.perf_counter()
    ocr_results: dict[str, list[Any]] = {}
    ocr_skipped: dict[str, bool] = {}
    for key in ("team", "all"):
        mask = masks[key]
        should_run = True if should_run_ocr is None else should_run_ocr(mask, cfg)
        ocr_skipped[key] = not should_run
        ocr_results[key] = ocr.run(mask) if should_run else []
    ocr_seconds = time.perf_counter() - ocr_started

    parse_started = time.perf_counter()
    reconstructed = {
        key: reconstruct_line_data(ocr_results[key], cfg)
        for key in ("team", "all")
    }
    out = {
        key: [str(line["text"]) for line in lines]
        for key, (lines, _) in reconstructed.items()
    }
    raw_line_ys = {
        key: [float(line["center_y"]) for line in lines]
        for key, (lines, _) in reconstructed.items()
    }
    prefix_analysis = {
        key: compute_prefix_evidence_for_lines(masks[key], lines, median_h, cfg)
        for key, (lines, median_h) in reconstructed.items()
    }
    raw_channel_layouts = {
        key: layout
        for key, (layout, _) in prefix_analysis.items()
    }
    raw_line_prefix_evidence = {
        key: evidence
        for key, (_, evidence) in prefix_analysis.items()
    }

    gap_factor = cfg.get("max_continuation_y_gap_factor")
    raw_continuation_y_gaps: dict[str, float | None] = {
        key: gap_factor * median_h if gap_factor and median_h > 0.0 else None
        for key, (_, median_h) in reconstructed.items()
    }
    parse_seconds = time.perf_counter() - parse_started

    return {
        "config": cfg,
        "cropped_rgb_image": rgb_image,
        "masks": masks,
        "mask_debug_steps": mask_debug_steps,
        "ocr_results": ocr_results,
        "ocr_skipped": ocr_skipped,
        "raw_lines": out,
        "raw_line_ys": raw_line_ys,
        "raw_channel_layouts": raw_channel_layouts,
        "raw_line_prefix_evidence": raw_line_prefix_evidence,
        "raw_continuation_y_gaps": raw_continuation_y_gaps,
        "timings": {
            "preprocess_seconds": preprocess_seconds,
            "ocr_seconds": ocr_seconds,
            "parse_seconds": parse_seconds,
        },
    }


def extract_chat_lines(
    rgb_image: np.ndarray,
    ocr: OCRBackend,
    *,
    config_overrides: Optional[Mapping[str, Any]] = None,
    ocr_profile: ResolvedOCRProfile | None = None,
) -> dict[str, list[str]]:
    """Run masks + OCR + line reconstruction for team and all chat."""
    return extract_chat_debug_data(
        rgb_image,
        ocr,
        config_overrides=config_overrides,
        ocr_profile=ocr_profile,
    )["raw_lines"]
