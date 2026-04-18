"""T-34: verify GUI chat-color HSV settings propagate to every detection path.

These tests guard the chain

    GUI settings_panel --> save_ui_config --> config.json
    --> load_config + _normalize_ocr_config --> profile.pipeline
    --> merge_pipeline_config_for_profile --> create_chat_masks

A regression anywhere along that chain would silently no-op HSV edits made in the
GUI, so each link is exercised by a dedicated test.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

import ow_chat_logger.config as cfg_module
from ow_chat_logger.config import (
    _normalize_ocr_config,
    load_config,
    merge_runtime_config,
    resolve_ocr_profile,
)
from ow_chat_logger.gui.config_io import save_ui_config
from ow_chat_logger.image_processing import create_chat_masks
from ow_chat_logger.pipeline import (
    extract_chat_debug_data,
    merge_pipeline_config_for_profile,
)


_HSV_KEYS: tuple[str, ...] = (
    "team_hsv_lower",
    "team_hsv_upper",
    "all_hsv_lower",
    "all_hsv_upper",
)


def _hsv_synthetic_frame() -> np.ndarray:
    """3x3 RGB frame where each pixel has a known HSV.

    Built so it covers both the default team (blue) range and an intentionally
    narrow synthetic range the tests swap in.
    """
    hsv = np.zeros((1, 3, 3), dtype=np.uint8)
    hsv[0, 0] = (100, 220, 200)  # inside the default team range
    hsv[0, 1] = (10, 220, 200)  # inside the default all range
    hsv[0, 2] = (150, 220, 200)  # outside both default ranges (magenta-ish)
    import cv2

    return cv2.cvtColor(hsv, cv2.COLOR_HSV2RGB)


# A narrow range no pixel in _hsv_synthetic_frame lies inside, used whenever a
# test needs to assert a range produces an empty mask. Picked so no component
# overlaps any of the three synthetic pixels.
_EMPTY_RANGE_LOWER: list[int] = [178, 250, 250]
_EMPTY_RANGE_UPPER: list[int] = [179, 255, 255]


class _StubOCR:
    def run(self, _mask):
        return []


# ──────────────────────────────────────────────────────────────────────────────
# Link 1: create_chat_masks reads HSV directly from the cfg it is handed
# ──────────────────────────────────────────────────────────────────────────────


def test_create_chat_masks_reads_hsv_from_cfg_dict():
    frame = _hsv_synthetic_frame()

    wide_cfg = {
        "team_hsv_lower": [0, 0, 0],
        "team_hsv_upper": [179, 255, 255],
        "all_hsv_lower": [0, 0, 0],
        "all_hsv_upper": [179, 255, 255],
    }
    blue_wide, _ = create_chat_masks(frame, wide_cfg)
    assert int(blue_wide.sum()) > 0, "wide mask should include every non-black pixel"

    narrow_cfg = {
        "team_hsv_lower": _EMPTY_RANGE_LOWER,
        "team_hsv_upper": _EMPTY_RANGE_UPPER,
        "all_hsv_lower": _EMPTY_RANGE_LOWER,
        "all_hsv_upper": _EMPTY_RANGE_UPPER,
    }
    blue_narrow, orange_narrow = create_chat_masks(frame, narrow_cfg)
    assert int(blue_narrow.sum()) == 0
    assert int(orange_narrow.sum()) == 0


# ──────────────────────────────────────────────────────────────────────────────
# Link 2: extract_chat_debug_data honors overrides that mutate HSV keys
# ──────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("channel", ["team", "all"])
def test_extract_chat_debug_data_respects_hsv_overrides(channel: str):
    frame = _hsv_synthetic_frame()

    wide_overrides = {
        "screen_region": [0, 0, frame.shape[1], frame.shape[0]],
        "team_hsv_lower": [0, 0, 0] if channel == "team" else _EMPTY_RANGE_LOWER,
        "team_hsv_upper": [179, 255, 255] if channel == "team" else _EMPTY_RANGE_UPPER,
        "all_hsv_lower": [0, 0, 0] if channel == "all" else _EMPTY_RANGE_LOWER,
        "all_hsv_upper": [179, 255, 255] if channel == "all" else _EMPTY_RANGE_UPPER,
    }
    debug = extract_chat_debug_data(
        frame,
        _StubOCR(),
        config_overrides=wide_overrides,
        pre_cropped=True,
    )
    assert int(debug["masks"][channel].sum()) > 0

    closed_overrides = {
        **wide_overrides,
        f"{channel}_hsv_lower": _EMPTY_RANGE_LOWER,
        f"{channel}_hsv_upper": _EMPTY_RANGE_UPPER,
    }
    debug_closed = extract_chat_debug_data(
        frame,
        _StubOCR(),
        config_overrides=closed_overrides,
        pre_cropped=True,
    )
    assert int(debug_closed["masks"][channel].sum()) == 0


# ──────────────────────────────────────────────────────────────────────────────
# Link 3: legacy flat HSV keys in user config propagate into profile.pipeline
# ──────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("key", _HSV_KEYS)
def test_flat_hsv_keys_propagate_into_profile_pipeline(key: str):
    synthetic = [7, 11, 13] if key.endswith("_lower") else [170, 250, 240]
    merged = merge_runtime_config({key: synthetic})
    profile = resolve_ocr_profile(merged)
    assert profile.pipeline[key] == synthetic

    cfg_for_masks = merge_pipeline_config_for_profile(profile=profile)
    assert cfg_for_masks[key] == synthetic


def test_flat_hsv_keys_ignored_when_user_sets_explicit_ocr_profiles():
    """Documents the silent no-op failure mode called out in T-34.

    When the user's config has ``ocr.profiles`` explicitly set, the legacy flat
    HSV keys are NOT merged into the profile pipeline. A future task can fix
    this; this test exists to fail loudly if the behavior changes either way.
    """
    user_data = {
        "team_hsv_lower": [7, 11, 13],
        "ocr": {"profiles": {"custom": {"engine": "windows", "pipeline": {}}}},
    }
    raw = {**cfg_module._DEFAULT_CONFIG, **user_data}
    normalized = _normalize_ocr_config(raw, user_data)
    default_profile = normalized["ocr"]["profiles"][cfg_module.DEFAULT_OCR_PROFILE]
    assert default_profile["pipeline"]["team_hsv_lower"] != [7, 11, 13]


# ──────────────────────────────────────────────────────────────────────────────
# Link 4: end-to-end — GUI write reaches create_chat_masks through the real
# config-file round trip. This is the test the user asked for explicitly:
# "make sure the color pickers in the ui affect the values".
# ──────────────────────────────────────────────────────────────────────────────


def test_gui_hsv_write_reaches_create_chat_masks(tmp_path: Path, monkeypatch):
    config_path = tmp_path / "config.json"
    monkeypatch.setenv("OW_CHAT_LOGGER_CONFIG", str(config_path))
    cfg_module.reset_config()

    synthetic = {
        "team_hsv_lower": [5, 10, 15],
        "team_hsv_upper": [25, 200, 220],
        "all_hsv_lower": [100, 110, 120],
        "all_hsv_upper": [130, 240, 250],
    }
    save_ui_config(synthetic)
    assert json.loads(config_path.read_text(encoding="utf-8"))["team_hsv_lower"] == [5, 10, 15]

    loaded = load_config(reload=True)
    for key, value in synthetic.items():
        assert loaded[key] == value, f"flat {key} missing from reloaded CONFIG"

    profile = resolve_ocr_profile(loaded)
    cfg_for_masks = merge_pipeline_config_for_profile(profile=profile)
    for key, value in synthetic.items():
        assert cfg_for_masks[key] == value, (
            f"GUI write for {key} did not reach the mask-building cfg"
        )

    frame = _hsv_synthetic_frame()
    blue_before, _ = create_chat_masks(frame, cfg_for_masks)
    baseline_blue_sum = int(blue_before.sum())

    closed = {
        **synthetic,
        "team_hsv_lower": _EMPTY_RANGE_LOWER,
        "team_hsv_upper": _EMPTY_RANGE_UPPER,
    }
    save_ui_config(closed)
    loaded2 = load_config(reload=True)
    cfg2 = merge_pipeline_config_for_profile(profile=resolve_ocr_profile(loaded2))
    blue_after, _ = create_chat_masks(frame, cfg2)
    assert int(blue_after.sum()) == 0, (
        "closing the team HSV range in the GUI must produce an empty team mask; "
        f"got {int(blue_after.sum())} non-zero pixels (baseline was {baseline_blue_sum})"
    )

    cfg_module.reset_config()
