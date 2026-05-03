"""Image pipeline helpers (no OCR)."""

import numpy as np

from ow_chat_logger.image_processing import (
    clean_mask,
    compute_prefix_evidence_for_lines,
    reconstruct_line_data,
    reconstruct_lines,
    remove_small_components,
)


def _box(x0, y0, w, h):
    return np.array([[x0, y0], [x0 + w, y0], [x0 + w, y0 + h], [x0, y0 + h]], dtype=np.float32)


def test_reconstruct_lines_merges_same_row():
    cfg = {"y_merge_threshold": 100}
    results = [
        (_box(0, 0, 10, 10), "hello", 0.9),
        (_box(50, 2, 10, 10), "world", 0.9),
    ]
    lines = reconstruct_lines(results, cfg)
    assert lines == ["hello world"]


def test_reconstruct_lines_splits_different_rows():
    cfg = {"y_merge_threshold": 5}
    results = [
        (_box(0, 0, 10, 10), "a", 0.9),
        (_box(0, 50, 10, 10), "b", 0.9),
    ]
    lines = reconstruct_lines(results, cfg)
    assert lines == ["a", "b"]


def test_reconstruct_lines_empty():
    assert reconstruct_lines([], {"y_merge_threshold": 10}) == []


def test_reconstruct_lines_filters_subheight_line_via_median():
    """A line whose max bounding-box height is below (fraction × median) is discarded.

    box1: center-y=35, height=70 → line max height 70
    box2: center-y=65, height=10 → separate line (diff 30 > y_merge_threshold=20), max height 10
    median of line heights = median([70, 10]) = 40
    threshold = 0.55 × 40 = 22 → box2 line (height 10) < 22 → filtered.
    """
    cfg = {"y_merge_threshold": 20, "min_box_height_fraction": 0.55}
    results = [
        (_box(0, 0, 200, 70), "[Alice]: hello", 0.9),
        (_box(210, 60, 80, 10), "enekleA", 0.8),
    ]
    lines = reconstruct_lines(results, cfg)
    assert lines == ["[Alice]: hello"]


def test_reconstruct_lines_drops_subheight_line_below_fraction_threshold():
    """A line whose max height is below (fraction × median) is dropped.

    line1: height=80 (normal), line2: height=20 (garbage, 25% of normal).
    median([80, 20]) = 50, threshold = 0.5 × 50 = 25 → 20 < 25 → filtered.
    """
    cfg = {"y_merge_threshold": 20, "min_box_height_fraction": 0.5}
    results = [
        (_box(0, 0, 200, 80), "[Alice]: hello", 0.9),
        (_box(0, 300, 120, 20), "garbage", 0.9),
    ]

    lines = reconstruct_lines(results, cfg)

    assert lines == ["[Alice]: hello"]


def test_reconstruct_lines_keeps_line_above_fraction_threshold():
    """A line whose max height is at or above (fraction × median) is kept.

    line1: height=80, line2: height=70 (87% of median ≈ 75).
    median([80, 70]) = 75, threshold = 0.5 × 75 = 37.5 → 70 > 37.5 → kept.
    """
    cfg = {"y_merge_threshold": 20, "min_box_height_fraction": 0.5}
    results = [
        (_box(0, 0, 200, 80), "[Alice]: hello", 0.9),
        (_box(0, 200, 120, 70), "[Bob]: world", 0.9),
    ]

    lines = reconstruct_lines(results, cfg)

    assert lines == ["[Alice]: hello", "[Bob]: world"]


def test_reconstruct_lines_sliding_y_anchor():
    """Boxes at y=[0,15,30] with threshold=18 should merge into one line.

    With a fixed group-start anchor, y=30 is compared against y=0 (diff=30>18)
    and splits incorrectly. A sliding anchor compares y=30 against y=15 (diff=15<18).
    """
    cfg = {"y_merge_threshold": 18}
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
    cfg = {"y_merge_threshold": 14}
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


def test_reconstruct_line_data_exposes_geometry():
    cfg = {"y_merge_threshold": 20}
    results = [
        (_box(40, 10, 30, 20), "hello", 0.9),
        (_box(80, 12, 20, 18), "world", 0.9),
    ]

    lines, median_h = reconstruct_line_data(results, cfg)

    assert median_h == 20.0
    assert lines == [
        {
            "text": "hello world",
            "center_y": 20.0,
            "top_y": 10.0,
            "bottom_y": 30.0,
            "line_height": 20.0,
            "first_box_x": 40.0,
            "first_box_right_x": 70.0,
            "segments": [
                {"text": "hello", "x1": 40.0, "x2": 70.0, "y1": 10.0, "y2": 30.0},
                {"text": "world", "x1": 80.0, "x2": 100.0, "y1": 12.0, "y2": 30.0},
            ],
        }
    ]


def test_compute_prefix_evidence_for_lines_positive_case():
    mask = np.zeros((120, 160), dtype=np.uint8)
    mask[30:70, 10:16] = 255
    mask[30:70, 18:24] = 255
    mask[30:70, 26:30] = 255

    layout, evidence = compute_prefix_evidence_for_lines(
        mask,
        [
            {
                "text": "[A]: hi",
                "center_y": 20.0,
                "top_y": 4.0,
                "bottom_y": 36.0,
                "line_height": 32.0,
                "first_box_x": 10.0,
                "first_box_right_x": 42.0,
                "segments": [
                    {"text": "[A]:", "x1": 10.0, "x2": 42.0, "y1": 4.0, "y2": 36.0},
                    {"text": "hi", "x1": 70.0, "x2": 92.0, "y1": 8.0, "y2": 34.0},
                ],
            },
            {
                "text": "[LongName]: hey",
                "center_y": 60.0,
                "top_y": 44.0,
                "bottom_y": 76.0,
                "line_height": 32.0,
                "first_box_x": 12.0,
                "first_box_right_x": 58.0,
                "segments": [
                    {"text": "[Long", "x1": 12.0, "x2": 34.0, "y1": 44.0, "y2": 76.0},
                    {"text": "Name]:", "x1": 35.0, "x2": 58.0, "y1": 44.0, "y2": 76.0},
                    {"text": "hey", "x1": 80.0, "x2": 102.0, "y1": 48.0, "y2": 74.0},
                ],
            },
            {
                "text": "YO",
                "center_y": 50.0,
                "top_y": 34.0,
                "bottom_y": 66.0,
                "line_height": 32.0,
                "first_box_x": 80.0,
                "first_box_right_x": 104.0,
                "segments": [
                    {"text": "YO", "x1": 80.0, "x2": 104.0, "y1": 34.0, "y2": 66.0},
                ],
            },
        ],
        median_line_h=32.0,
        config={
            "missing_prefix_min_anchor_lines": 2,
            "missing_prefix_body_start_tolerance": 4.0,
            "missing_prefix_span_right_padding": 4,
            "missing_prefix_vertical_padding": 4,
            "missing_prefix_min_span_nonzero_pixels": 500,
            "missing_prefix_min_span_density": 0.2,
            "missing_prefix_max_span_density": 0.5,
            "missing_prefix_max_largest_component_fraction": 0.8,
            "missing_prefix_min_line_height_fraction": 0.8,
            "missing_prefix_max_line_height_fraction": 1.2,
        },
    )

    assert layout["has_learned_layout"] is True
    assert layout["anchor_count"] == 2
    assert evidence[-1]["has_missing_prefix_evidence"] is True
    assert evidence[-1]["within_body_start_range"] is True
    assert evidence[-1]["probe_nonzero_pixels"] > 0
    assert evidence[-1]["probe_density"] > 0.2


def test_compute_prefix_evidence_for_lines_single_anchor_recovers_with_strict_density():
    """With min_anchor_lines=1 and a stricter min_density, a single-anchor channel
    can still detect a missing-prefix continuation. Mirrors the ex_23/ex_24 shape:
    only one parseable prefix in the channel (`[Power]:`), and a bare body line
    (`epic!`) below it that should split into [unknown]: epic! rather than merge.
    """
    mask = np.zeros((120, 200), dtype=np.uint8)
    # anchor [Power]: row at y=4..36 — three vertical strips (high density)
    mask[4:36, 10:16] = 255
    mask[4:36, 18:24] = 255
    mask[4:36, 26:32] = 255
    # missing-prefix probe row at y=44..76 — three strips of similar density
    mask[44:76, 12:18] = 255
    mask[44:76, 20:26] = 255
    mask[44:76, 28:34] = 255

    layout, evidence = compute_prefix_evidence_for_lines(
        mask,
        [
            {
                "text": "[Power]: msg",
                "center_y": 20.0,
                "top_y": 4.0,
                "bottom_y": 36.0,
                "line_height": 32.0,
                "first_box_x": 10.0,
                "first_box_right_x": 50.0,
                "segments": [
                    {"text": "[Power]:", "x1": 10.0, "x2": 50.0, "y1": 4.0, "y2": 36.0},
                    {"text": "msg", "x1": 80.0, "x2": 110.0, "y1": 8.0, "y2": 34.0},
                ],
            },
            {
                "text": "epicl",
                "center_y": 60.0,
                "top_y": 44.0,
                "bottom_y": 76.0,
                "line_height": 32.0,
                "first_box_x": 80.0,
                "first_box_right_x": 110.0,
                "segments": [
                    {"text": "epicl", "x1": 80.0, "x2": 110.0, "y1": 44.0, "y2": 76.0},
                ],
            },
        ],
        median_line_h=32.0,
        config={
            "missing_prefix_min_anchor_lines": 1,
            "missing_prefix_body_start_tolerance": 4.0,
            "missing_prefix_span_right_padding": 4,
            "missing_prefix_vertical_padding": 4,
            "missing_prefix_min_span_nonzero_pixels": 100,
            "missing_prefix_min_span_density": 0.20,
            "missing_prefix_max_span_density": 0.5,
            "missing_prefix_max_largest_component_fraction": 0.8,
            "missing_prefix_min_line_height_fraction": 0.8,
            "missing_prefix_max_line_height_fraction": 1.2,
        },
    )

    assert layout["has_learned_layout"] is True
    assert layout["anchor_count"] == 1
    assert evidence[1]["has_missing_prefix_evidence"] is True
    assert evidence[1]["within_body_start_range"] is True


def test_compute_prefix_evidence_for_lines_single_anchor_skips_body_start_range_check():
    """With only one anchor, body_start_range is derived from a single sample and
    cannot account for player-name length variance. A short missing prefix
    (e.g. [A7X]:) produces a body that starts well to the LEFT of where a long
    anchor (e.g. [Power]:) puts its body — within_body_start_range is False but
    the heuristic should still fire because the probe density is strong.
    Mirrors the actual ex_23/ex_24 root cause."""
    mask = np.zeros((120, 200), dtype=np.uint8)
    # anchor [Power]: at y=4..36 — body starts at x=80
    mask[4:36, 10:16] = 255
    mask[4:36, 18:24] = 255
    mask[4:36, 26:32] = 255
    # missing-prefix probe row at y=44..76 — body would start at x=50 (short prefix
    # like [A7X]: instead of [Power]:). Strong probe density in the prefix region.
    mask[44:76, 12:18] = 255
    mask[44:76, 20:26] = 255
    mask[44:76, 28:34] = 255

    layout, evidence = compute_prefix_evidence_for_lines(
        mask,
        [
            {
                "text": "[Power]: msg",
                "center_y": 20.0,
                "top_y": 4.0,
                "bottom_y": 36.0,
                "line_height": 32.0,
                "first_box_x": 10.0,
                "first_box_right_x": 50.0,
                "segments": [
                    {"text": "[Power]:", "x1": 10.0, "x2": 50.0, "y1": 4.0, "y2": 36.0},
                    {"text": "msg", "x1": 80.0, "x2": 110.0, "y1": 8.0, "y2": 34.0},
                ],
            },
            {
                "text": "epicl",
                "center_y": 60.0,
                "top_y": 44.0,
                "bottom_y": 76.0,
                "line_height": 32.0,
                # body starts well to the left of the [Power]: body anchor (80) —
                # this would be False on within_body_start_range.
                "first_box_x": 50.0,
                "first_box_right_x": 80.0,
                "segments": [
                    {"text": "epicl", "x1": 50.0, "x2": 80.0, "y1": 44.0, "y2": 76.0},
                ],
            },
        ],
        median_line_h=32.0,
        config={
            "missing_prefix_min_anchor_lines": 1,
            "missing_prefix_body_start_tolerance": 4.0,
            "missing_prefix_span_right_padding": 4,
            "missing_prefix_vertical_padding": 4,
            "missing_prefix_min_span_nonzero_pixels": 100,
            "missing_prefix_min_span_density": 0.20,
            "missing_prefix_max_span_density": 0.5,
            "missing_prefix_max_largest_component_fraction": 0.8,
            "missing_prefix_min_line_height_fraction": 0.8,
            "missing_prefix_max_line_height_fraction": 1.2,
        },
    )

    assert layout["anchor_count"] == 1
    assert evidence[1]["within_body_start_range"] is False  # outside the narrow range
    assert evidence[1]["has_missing_prefix_evidence"] is True  # but heuristic fires anyway


def test_compute_prefix_evidence_for_lines_single_anchor_rejected_when_density_low():
    """The stricter min_density (0.20) that pairs with min_anchor_lines=1 must reject
    a probe region that would have passed the old 0.12 threshold. Guards against
    spurious missing-prefix splits in sparse channels with weak background mask."""
    mask = np.zeros((120, 200), dtype=np.uint8)
    # anchor row — strong prefix mask
    mask[4:36, 10:16] = 255
    mask[4:36, 18:24] = 255
    mask[4:36, 26:32] = 255
    # probe row with density ~0.15 (above old 0.12 floor, below new 0.20 floor)
    mask[44:76, 14:18] = 255
    mask[44:76, 22:26] = 255

    _, evidence = compute_prefix_evidence_for_lines(
        mask,
        [
            {
                "text": "[Power]: msg",
                "center_y": 20.0,
                "top_y": 4.0,
                "bottom_y": 36.0,
                "line_height": 32.0,
                "first_box_x": 10.0,
                "first_box_right_x": 50.0,
                "segments": [
                    {"text": "[Power]:", "x1": 10.0, "x2": 50.0, "y1": 4.0, "y2": 36.0},
                    {"text": "msg", "x1": 80.0, "x2": 110.0, "y1": 8.0, "y2": 34.0},
                ],
            },
            {
                "text": "weak",
                "center_y": 60.0,
                "top_y": 44.0,
                "bottom_y": 76.0,
                "line_height": 32.0,
                "first_box_x": 80.0,
                "first_box_right_x": 110.0,
                "segments": [
                    {"text": "weak", "x1": 80.0, "x2": 110.0, "y1": 44.0, "y2": 76.0},
                ],
            },
        ],
        median_line_h=32.0,
        config={
            "missing_prefix_min_anchor_lines": 1,
            "missing_prefix_body_start_tolerance": 4.0,
            "missing_prefix_span_right_padding": 4,
            "missing_prefix_vertical_padding": 4,
            "missing_prefix_min_span_nonzero_pixels": 100,
            "missing_prefix_min_span_density": 0.20,
            "missing_prefix_max_span_density": 0.5,
            "missing_prefix_max_largest_component_fraction": 0.8,
            "missing_prefix_min_line_height_fraction": 0.8,
            "missing_prefix_max_line_height_fraction": 1.2,
        },
    )

    assert evidence[1]["has_missing_prefix_evidence"] is False
    assert evidence[1]["probe_density"] < 0.20


def test_compute_prefix_evidence_for_lines_negative_case_without_anchors():
    mask = np.zeros((120, 160), dtype=np.uint8)
    mask[30:70, 10:30] = 255

    layout, evidence = compute_prefix_evidence_for_lines(
        mask,
        [
            {
                "text": "continuation",
                "center_y": 50.0,
                "top_y": 34.0,
                "bottom_y": 66.0,
                "line_height": 32.0,
                "first_box_x": 90.0,
                "first_box_right_x": 114.0,
                "segments": [
                    {"text": "continuation", "x1": 90.0, "x2": 114.0, "y1": 34.0, "y2": 66.0},
                ],
            }
        ],
        median_line_h=32.0,
        config={
            "missing_prefix_min_anchor_lines": 2,
        },
    )

    assert layout["has_learned_layout"] is False
    assert evidence[0]["has_missing_prefix_evidence"] is False


def test_compute_prefix_evidence_for_lines_negative_case_outside_body_start_range():
    mask = np.zeros((120, 200), dtype=np.uint8)
    mask[30:70, 10:44] = 255

    _, evidence = compute_prefix_evidence_for_lines(
        mask,
        [
            {
                "text": "[A]: hi",
                "center_y": 20.0,
                "top_y": 4.0,
                "bottom_y": 36.0,
                "line_height": 32.0,
                "first_box_x": 10.0,
                "first_box_right_x": 42.0,
                "segments": [
                    {"text": "[A]:", "x1": 10.0, "x2": 42.0, "y1": 4.0, "y2": 36.0},
                    {"text": "hi", "x1": 70.0, "x2": 92.0, "y1": 8.0, "y2": 34.0},
                ],
            },
            {
                "text": "[LongName]: hey",
                "center_y": 60.0,
                "top_y": 44.0,
                "bottom_y": 76.0,
                "line_height": 32.0,
                "first_box_x": 12.0,
                "first_box_right_x": 58.0,
                "segments": [
                    {"text": "[Long", "x1": 12.0, "x2": 34.0, "y1": 44.0, "y2": 76.0},
                    {"text": "Name]:", "x1": 35.0, "x2": 58.0, "y1": 44.0, "y2": 76.0},
                    {"text": "hey", "x1": 80.0, "x2": 102.0, "y1": 48.0, "y2": 74.0},
                ],
            },
            {
                "text": "noise",
                "center_y": 50.0,
                "top_y": 34.0,
                "bottom_y": 66.0,
                "line_height": 32.0,
                "first_box_x": 130.0,
                "first_box_right_x": 150.0,
                "segments": [
                    {"text": "noise", "x1": 130.0, "x2": 150.0, "y1": 34.0, "y2": 66.0},
                ],
            },
        ],
        median_line_h=32.0,
        config={
            "missing_prefix_min_anchor_lines": 2,
            "missing_prefix_body_start_tolerance": 4.0,
            "missing_prefix_span_right_padding": 4,
            "missing_prefix_vertical_padding": 4,
            "missing_prefix_min_span_nonzero_pixels": 500,
            "missing_prefix_min_span_density": 0.2,
            "missing_prefix_max_span_density": 0.5,
            "missing_prefix_max_largest_component_fraction": 0.8,
            "missing_prefix_min_line_height_fraction": 0.8,
            "missing_prefix_max_line_height_fraction": 1.2,
        },
    )

    assert evidence[-1]["within_body_start_range"] is False
    assert evidence[-1]["has_missing_prefix_evidence"] is False


def test_compute_prefix_evidence_for_lines_negative_case_blob_rejected():
    mask = np.zeros((120, 160), dtype=np.uint8)
    mask[30:70, 10:76] = 255

    _, evidence = compute_prefix_evidence_for_lines(
        mask,
        [
            {
                "text": "[A]: hi",
                "center_y": 20.0,
                "top_y": 4.0,
                "bottom_y": 36.0,
                "line_height": 32.0,
                "first_box_x": 10.0,
                "first_box_right_x": 42.0,
                "segments": [
                    {"text": "[A]:", "x1": 10.0, "x2": 42.0, "y1": 4.0, "y2": 36.0},
                    {"text": "hi", "x1": 70.0, "x2": 92.0, "y1": 8.0, "y2": 34.0},
                ],
            },
            {
                "text": "[B]: yo",
                "center_y": 60.0,
                "top_y": 44.0,
                "bottom_y": 76.0,
                "line_height": 32.0,
                "first_box_x": 10.0,
                "first_box_right_x": 42.0,
                "segments": [
                    {"text": "[B]:", "x1": 10.0, "x2": 42.0, "y1": 44.0, "y2": 76.0},
                    {"text": "yo", "x1": 72.0, "x2": 94.0, "y1": 48.0, "y2": 74.0},
                ],
            },
            {
                "text": "garbage",
                "center_y": 50.0,
                "top_y": 34.0,
                "bottom_y": 66.0,
                "line_height": 32.0,
                "first_box_x": 80.0,
                "first_box_right_x": 104.0,
                "segments": [
                    {"text": "garbage", "x1": 80.0, "x2": 104.0, "y1": 34.0, "y2": 66.0},
                ],
            },
        ],
        median_line_h=32.0,
        config={
            "missing_prefix_min_anchor_lines": 2,
            "missing_prefix_body_start_tolerance": 4.0,
            "missing_prefix_span_right_padding": 4,
            "missing_prefix_vertical_padding": 4,
            "missing_prefix_min_span_nonzero_pixels": 500,
            "missing_prefix_min_span_density": 0.2,
            "missing_prefix_max_span_density": 0.5,
            "missing_prefix_max_largest_component_fraction": 0.8,
            "missing_prefix_min_line_height_fraction": 0.8,
            "missing_prefix_max_line_height_fraction": 1.2,
        },
    )

    assert evidence[-1]["probe_density"] > 0.5
    assert evidence[-1]["probe_largest_component_fraction"] > 0.8
    assert evidence[-1]["has_missing_prefix_evidence"] is False


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

    cleaned = clean_mask(
        mask, {"scale_factor": 2, "high_quality_ocr": True, "min_component_area": 0}
    )

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
