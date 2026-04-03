"""Image pipeline helpers (no OCR)."""

import numpy as np

from ow_chat_logger.image_processing import clean_mask, reconstruct_lines, remove_small_components


def _box(x0, y0, w, h):
    return np.array([[x0, y0], [x0 + w, y0], [x0 + w, y0 + h], [x0, y0 + h]], dtype=np.float32)


def test_reconstruct_lines_merges_same_row():
    cfg = {"y_merge_threshold": 100, "min_ocr_box_height": 0}
    results = [
        (_box(0, 0, 10, 10), "hello", 0.9),
        (_box(50, 2, 10, 10), "world", 0.9),
    ]
    lines = reconstruct_lines(results, cfg)
    assert lines == ["hello world"]


def test_reconstruct_lines_splits_different_rows():
    cfg = {"y_merge_threshold": 5, "min_ocr_box_height": 0}
    results = [
        (_box(0, 0, 10, 10), "a", 0.9),
        (_box(0, 50, 10, 10), "b", 0.9),
    ]
    lines = reconstruct_lines(results, cfg)
    assert lines == ["a", "b"]


def test_reconstruct_lines_empty():
    assert reconstruct_lines([], {"y_merge_threshold": 10}) == []


def test_reconstruct_lines_drops_short_line_below_min_height():
    cfg = {"y_merge_threshold": 20, "min_ocr_box_height": 60}
    results = [
        (_box(0, 0, 200, 72), "[Alice]: hello", 0.9),
        (_box(500, 300, 120, 42), "Moico chat", 0.9),
    ]

    lines = reconstruct_lines(results, cfg)

    assert lines == ["[Alice]: hello"]


def test_reconstruct_lines_keeps_line_at_or_above_min_height():
    cfg = {"y_merge_threshold": 20, "min_ocr_box_height": 60}
    results = [
        (_box(0, 0, 200, 72), "[Alice]: hello", 0.9),
        (_box(500, 120, 120, 66), "epci", 0.9),
    ]

    lines = reconstruct_lines(results, cfg)

    assert lines == ["[Alice]: hello", "epci"]


def test_reconstruct_lines_sliding_y_anchor():
    """Boxes at y=[0,15,30] with threshold=18 should merge into one line.

    With a fixed group-start anchor, y=30 is compared against y=0 (diff=30>18)
    and splits incorrectly. A sliding anchor compares y=30 against y=15 (diff=15<18).
    """
    cfg = {"y_merge_threshold": 18, "min_ocr_box_height": 0}
    results = [
        (_box(0, 0, 10, 10), "a", 0.9),
        (_box(20, 15, 10, 10), "b", 0.9),
        (_box(40, 30, 10, 10), "c", 0.9),
    ]
    lines = reconstruct_lines(results, cfg)
    assert lines == ["a b c"]


def test_reconstruct_lines_short_char_stays_on_same_line():
    """Short characters (e.g. 'u') whose top-y is lower than tall neighbours
    must still be grouped on the same visual line.

    'fck' and 'moira' have top-y=0 (tall glyphs); 'u' has top-y=20 (short glyph)
    but its center-y (~30) is within threshold of its neighbours' center-y (~20).
    With threshold=14, top-y grouping misclassifies 'u' into a separate group
    (diff=20 > 14), while center-y grouping correctly keeps it with the line.
    """
    cfg = {"y_merge_threshold": 14, "min_ocr_box_height": 0}
    # tall box: top=0, height=40 → center_y=20
    # short box: top=20, height=20 → center_y=30  (top-y diff from fck = 20 > 14)
    # tall box: top=2, height=36 → center_y=20
    results = [
        (_box(0, 0, 30, 40), "fck", 0.9),
        (_box(40, 20, 10, 20), "u", 0.9),
        (_box(60, 2, 40, 36), "moira", 0.9),
    ]
    lines = reconstruct_lines(results, cfg)
    assert lines == ["fck u moira"]


def test_remove_small_components_drops_tiny_islands():
    mask = np.zeros((8, 8), dtype=np.uint8)
    mask[0, 0] = 255
    mask[2:5, 2:5] = 255

    cleaned = remove_small_components(mask, min_area=4)

    assert cleaned[0, 0] == 0
    assert np.all(cleaned[2:5, 2:5] == 255)


def test_remove_small_components_keeps_mask_when_threshold_disabled():
    mask = np.zeros((4, 4), dtype=np.uint8)
    mask[0, 0] = 255

    cleaned = remove_small_components(mask, min_area=0)

    assert np.array_equal(cleaned, mask)


def test_clean_mask_high_quality_mode_uses_larger_effective_scale():
    mask = np.zeros((2, 2), dtype=np.uint8)
    mask[0, 0] = 255

    cleaned = clean_mask(mask, {"scale_factor": 2, "high_quality_ocr": True, "min_component_area": 0})

    assert cleaned.shape == (6, 6)


def test_clean_mask_high_quality_mode_removes_isolated_speckles():
    mask = np.zeros((4, 6), dtype=np.uint8)
    mask[0, 0] = 255

    cleaned = clean_mask(
        mask,
        {
            "scale_factor": 2,
            "high_quality_ocr": True,
            "min_component_area": 21,
        },
    )

    assert np.count_nonzero(cleaned) == 0
