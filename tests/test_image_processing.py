"""Image pipeline helpers (no OCR)."""

import numpy as np

from ow_chat_logger.image_processing import reconstruct_lines


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
