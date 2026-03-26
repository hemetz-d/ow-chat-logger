"""Pipeline extraction with mocked OCR (fast, deterministic)."""

from unittest.mock import MagicMock

import numpy as np
import pytest

from ow_chat_logger.pipeline import (
    crop_to_screen_region,
    extract_chat_lines,
    merge_pipeline_config,
)


def test_merge_pipeline_config_overrides_defaults():
    from ow_chat_logger.config import CONFIG

    m = merge_pipeline_config({"scale_factor": 99})
    assert m["scale_factor"] == 99
    assert m["languages"] == CONFIG["languages"]


def test_extract_chat_lines_uses_ocr_per_channel():
    ocr = MagicMock()
    # Two calls: team mask, all mask
    ocr.run.side_effect = [
        [([[0, 0], [10, 0], [10, 10], [0, 10]], "team_hi", 0.99)],
        [([[0, 0], [10, 0], [10, 10], [0, 10]], "all_bye", 0.99)],
    ]

    img = np.zeros((100, 100, 3), dtype=np.uint8)
    out = extract_chat_lines(
        img,
        ocr,
        config_overrides={
            "team_hsv_lower": [0, 0, 0],
            "team_hsv_upper": [179, 255, 255],
            "all_hsv_lower": [0, 0, 0],
            "all_hsv_upper": [179, 255, 255],
            "scale_factor": 1,
            "y_merge_threshold": 100,
        },
    )

    assert ocr.run.call_count == 2
    assert out["team"] == ["team_hi"]
    assert out["all"] == ["all_bye"]


def test_crop_to_screen_region_crops_full_screen_image():
    image = np.arange(1080 * 1920 * 3, dtype=np.uint8).reshape((1080, 1920, 3))

    cropped = crop_to_screen_region(
        image,
        {"screen_region": (50, 400, 500, 600)},
    )

    assert cropped.shape == (600, 500, 3)
    assert np.array_equal(cropped, image[400:1000, 50:550])


def test_crop_to_screen_region_keeps_pre_cropped_image_when_region_does_not_fit():
    image = np.zeros((600, 500, 3), dtype=np.uint8)

    cropped = crop_to_screen_region(
        image,
        {"screen_region": (50, 400, 500, 600)},
    )

    assert cropped is image
