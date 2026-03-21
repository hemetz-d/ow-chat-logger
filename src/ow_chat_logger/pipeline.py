"""Shared OCR pipeline: screenshot RGB → team / all chat line lists.

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


def extract_chat_lines(
    rgb_image: np.ndarray,
    ocr: OCREngine,
    *,
    config_overrides: Optional[Mapping[str, Any]] = None,
) -> dict[str, list[str]]:
    """Run masks + OCR + line reconstruction for team and all chat.

    Parameters
    ----------
    rgb_image
        H×W×3 uint8 RGB (same as ``pyautogui.screenshot`` after ``np.array``).
    ocr
        Initialized :class:`OCREngine` (can be CPU/GPU).
    config_overrides
        Partial config dict (e.g. ``scale_factor``, ``confidence_threshold``).
    """
    cfg = merge_pipeline_config(config_overrides)

    blue_mask, orange_mask = create_chat_masks(rgb_image, cfg)
    out: dict[str, list[str]] = {}

    for mask, key in [
        (clean_mask(blue_mask, cfg), "team"),
        (clean_mask(orange_mask, cfg), "all"),
    ]:
        results = ocr.run(mask)
        out[key] = reconstruct_lines(results, cfg)

    return out
