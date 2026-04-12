import json
from pathlib import Path
from unittest.mock import MagicMock

import numpy as np

from ow_chat_logger.analysis import run_analyze
from ow_chat_logger.ocr import ResolvedOCRProfile


def _fake_profile(name: str = "windows_default", engine_id: str = "windows") -> ResolvedOCRProfile:
    return ResolvedOCRProfile(
        name=name,
        engine_id=engine_id,
        languages=["en"],
        pipeline={"screen_region": (0, 0, 1, 1)},
        settings={},
    )


def test_run_analyze_writes_report_and_masks(monkeypatch, local_tmp_dir):
    tmp_dir = local_tmp_dir("analyze-artifacts")
    output_dir = tmp_dir / "analysis"
    image_path = tmp_dir / "sample.png"
    image_path.write_bytes(b"placeholder")
    rgb_image = np.zeros((2, 2, 3), dtype=np.uint8)

    monkeypatch.setattr("ow_chat_logger.analysis.load_rgb_image", lambda path: rgb_image)
    monkeypatch.setattr("ow_chat_logger.analysis.resolve_ocr_profile", lambda *args, **kwargs: _fake_profile())
    monkeypatch.setattr("ow_chat_logger.analysis.build_ocr_backend", lambda *args, **kwargs: object())
    monkeypatch.setattr(
        "ow_chat_logger.analysis.extract_chat_debug_data",
        lambda image, ocr, ocr_profile=None, config_overrides=None: {
            "config": {
                "languages": ["en"],
                "scale_factor": 3,
                "y_merge_threshold": 18,
                "team_hsv_lower": [1, 2, 3],
                "team_hsv_upper": [4, 5, 6],
                "all_hsv_lower": [7, 8, 9],
                "all_hsv_upper": [10, 11, 12],
            },
            "cropped_rgb_image": rgb_image,
            "masks": {
                "team": np.zeros((2, 2), dtype=np.uint8),
                "all": np.ones((2, 2), dtype=np.uint8),
            },
            "mask_debug_steps": {
                "team": [
                    ("01_raw_threshold", np.zeros((2, 2), dtype=np.uint8)),
                    ("02_upscaled", np.zeros((4, 4), dtype=np.uint8)),
                ],
                "all": [
                    ("01_raw_threshold", np.ones((2, 2), dtype=np.uint8)),
                    ("02_upscaled", np.ones((4, 4), dtype=np.uint8)),
                ],
            },
            "ocr_results": {
                "team": [([[0, 0], [1, 0], [1, 1], [0, 1]], "Alice", 1.0)],
                "all": [([[2, 2], [3, 2], [3, 3], [2, 3]], "Bob", None)],
            },
            "ocr_skipped": {"team": False, "all": True},
            "raw_line_ys": {"team": [10.0], "all": [20.0, 30.0]},
            "raw_channel_layouts": {
                "team": {
                    "anchor_count": 2,
                    "has_learned_layout": True,
                    "prefix_start_x": 45.0,
                    "body_start_range": [255.0, 281.0],
                    "anchor_prefix_start_xs": [45.0, 45.0],
                    "anchor_body_start_xs": [261.0, 277.0],
                    "anchor_span_widths": [216.0, 232.0],
                },
                "all": {
                    "anchor_count": 0,
                    "has_learned_layout": False,
                    "prefix_start_x": None,
                    "body_start_range": None,
                    "anchor_prefix_start_xs": [],
                    "anchor_body_start_xs": [],
                    "anchor_span_widths": [],
                },
            },
            "raw_line_prefix_evidence": {
                "team": [
                    {
                        "anchor_count": 2,
                        "prefix_start_x": 45.0,
                        "body_start_range": [255.0, 281.0],
                        "within_body_start_range": False,
                        "probe_rect": [1, 2, 3, 4],
                        "probe_nonzero_pixels": 12,
                        "probe_area": 24,
                        "probe_density": 0.5,
                        "probe_component_count": 2,
                        "probe_largest_component_fraction": 0.4,
                        "has_missing_prefix_evidence": False,
                        "first_box_x": 45.0,
                        "first_box_right_x": 100.0,
                        "top_y": 8.0,
                        "bottom_y": 18.0,
                        "line_height": 10.0,
                        "line_height_ratio": 1.0,
                        "within_line_height_range": True,
                    }
                ],
                "all": [
                    {
                        "anchor_count": 0,
                        "prefix_start_x": None,
                        "body_start_range": None,
                        "within_body_start_range": False,
                        "probe_rect": [5, 6, 7, 8],
                        "probe_nonzero_pixels": 30,
                        "probe_area": 60,
                        "probe_density": 0.5,
                        "probe_component_count": 1,
                        "probe_largest_component_fraction": 1.0,
                        "has_missing_prefix_evidence": True,
                        "first_box_x": 55.0,
                        "first_box_right_x": 88.0,
                        "top_y": 19.0,
                        "bottom_y": 29.0,
                        "line_height": 10.0,
                        "line_height_ratio": 1.0,
                        "within_line_height_range": True,
                    },
                    {
                        "anchor_count": 0,
                        "prefix_start_x": None,
                        "body_start_range": None,
                        "within_body_start_range": False,
                        "probe_rect": [9, 10, 11, 12],
                        "probe_nonzero_pixels": 0,
                        "probe_area": 20,
                        "probe_density": 0.0,
                        "probe_component_count": 0,
                        "probe_largest_component_fraction": 0.0,
                        "has_missing_prefix_evidence": False,
                        "first_box_x": 65.0,
                        "first_box_right_x": 95.0,
                        "top_y": 29.0,
                        "bottom_y": 39.0,
                        "line_height": 10.0,
                        "line_height_ratio": 1.0,
                        "within_line_height_range": True,
                    },
                ],
            },
            "raw_continuation_y_gaps": {"team": 15.0, "all": None},
            "timings": {
                "preprocess_seconds": 0.001,
                "ocr_seconds": 0.002,
                "parse_seconds": 0.003,
            },
            "raw_lines": {
                "team": ["[Alice] : hi there"],
                "all": ["Joined team voice chat - Push to talk", "[Bob] : hello"],
            },
        },
    )

    args = MagicMock(image=str(image_path), output_dir=str(output_dir), config=None)
    assert run_analyze(args) == 0

    report = json.loads((output_dir / "report.json").read_text(encoding="utf-8"))
    assert report["raw_lines"]["team"] == ["[Alice] : hi there"]
    assert report["ocr_profile"]["name"] == "windows_default"
    assert report["final_lines"] == {
        "team_lines": ["[Alice]: hi there"],
        "all_lines": ["[Bob]: hello"],
    }
    assert report["timings_ms"] == {
        "preprocess": 1.0,
        "ocr": 2.0,
        "parse": 3.0,
        "total": 6.0,
    }
    assert report["ocr_skipped"] == {"team": False, "all": True}
    assert report["mask_nonzero_pixels"] == {"team": 0, "all": 4}
    assert report["raw_line_ys"] == {"team": [10.0], "all": [20.0, 30.0]}
    assert report["raw_channel_layouts"] == {
        "team": {
            "anchor_count": 2,
            "has_learned_layout": True,
            "prefix_start_x": 45.0,
            "body_start_range": [255.0, 281.0],
            "anchor_prefix_start_xs": [45.0, 45.0],
            "anchor_body_start_xs": [261.0, 277.0],
            "anchor_span_widths": [216.0, 232.0],
        },
        "all": {
            "anchor_count": 0,
            "has_learned_layout": False,
            "prefix_start_x": None,
            "body_start_range": None,
            "anchor_prefix_start_xs": [],
            "anchor_body_start_xs": [],
            "anchor_span_widths": [],
        },
    }
    assert report["raw_line_prefix_evidence"] == {
        "team": [
            {
                "anchor_count": 2,
                "prefix_start_x": 45.0,
                "body_start_range": [255.0, 281.0],
                "within_body_start_range": False,
                "probe_rect": [1, 2, 3, 4],
                "probe_nonzero_pixels": 12,
                "probe_area": 24,
                "probe_density": 0.5,
                "probe_component_count": 2,
                "probe_largest_component_fraction": 0.4,
                "has_missing_prefix_evidence": False,
                "first_box_x": 45.0,
                "first_box_right_x": 100.0,
                "top_y": 8.0,
                "bottom_y": 18.0,
                "line_height": 10.0,
                "line_height_ratio": 1.0,
                "within_line_height_range": True,
            }
        ],
        "all": [
            {
                "anchor_count": 0,
                "prefix_start_x": None,
                "body_start_range": None,
                "within_body_start_range": False,
                "probe_rect": [5, 6, 7, 8],
                "probe_nonzero_pixels": 30,
                "probe_area": 60,
                "probe_density": 0.5,
                "probe_component_count": 1,
                "probe_largest_component_fraction": 1.0,
                "has_missing_prefix_evidence": True,
                "first_box_x": 55.0,
                "first_box_right_x": 88.0,
                "top_y": 19.0,
                "bottom_y": 29.0,
                "line_height": 10.0,
                "line_height_ratio": 1.0,
                "within_line_height_range": True,
            },
            {
                "anchor_count": 0,
                "prefix_start_x": None,
                "body_start_range": None,
                "within_body_start_range": False,
                "probe_rect": [9, 10, 11, 12],
                "probe_nonzero_pixels": 0,
                "probe_area": 20,
                "probe_density": 0.0,
                "probe_component_count": 0,
                "probe_largest_component_fraction": 0.0,
                "has_missing_prefix_evidence": False,
                "first_box_x": 65.0,
                "first_box_right_x": 95.0,
                "top_y": 29.0,
                "bottom_y": 39.0,
                "line_height": 10.0,
                "line_height_ratio": 1.0,
                "within_line_height_range": True,
            },
        ],
    }
    assert report["raw_continuation_y_gaps"] == {"team": 15.0, "all": None}
    assert report["ocr_results_serialized"] == {
        "team": [
            {
                "text": "Alice",
                "confidence": 1.0,
                "bbox": [[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0]],
            }
        ],
        "all": [
            {
                "text": "Bob",
                "confidence": None,
                "bbox": [[2.0, 2.0], [3.0, 2.0], [3.0, 3.0], [2.0, 3.0]],
            }
        ],
    }
    assert Path(report["artifacts"]["original_image"]).is_file()
    assert Path(report["artifacts"]["team_mask"]).is_file()
    assert Path(report["artifacts"]["all_mask"]).is_file()
    assert report["artifacts"]["mask_debug_steps"]["team"] == [
        str(output_dir / "team_01_raw_threshold.png"),
        str(output_dir / "team_02_upscaled.png"),
    ]
    assert report["artifacts"]["mask_debug_steps"]["all"] == [
        str(output_dir / "all_01_raw_threshold.png"),
        str(output_dir / "all_02_upscaled.png"),
    ]
    assert Path(report["artifacts"]["mask_debug_steps"]["team"][0]).is_file()
    assert Path(report["artifacts"]["mask_debug_steps"]["all"][1]).is_file()


def test_run_analyze_honors_json_overrides(monkeypatch, local_tmp_dir):
    tmp_dir = local_tmp_dir("analyze-overrides")
    image_path = tmp_dir / "sample.png"
    image_path.write_bytes(b"placeholder")
    config_path = tmp_dir / "override.json"
    config_path.write_text(
        json.dumps(
            {
                "languages": ["de"],
                "scale_factor": 4,
            }
        ),
        encoding="utf-8",
    )

    created = {}
    monkeypatch.setattr(
        "ow_chat_logger.analysis.load_rgb_image",
        lambda path: np.zeros((1, 1, 3), dtype=np.uint8),
    )

    def fake_build(profile):
        created["languages"] = profile.languages
        return object()

    monkeypatch.setattr(
        "ow_chat_logger.analysis.resolve_ocr_profile",
        lambda config, profile_name=None: ResolvedOCRProfile(
            name=profile_name or "windows_default",
            engine_id="windows",
            languages=list(config["languages"]),
            pipeline={"screen_region": (0, 0, 1, 1)},
            settings={},
        ),
    )
    monkeypatch.setattr("ow_chat_logger.analysis.build_ocr_backend", fake_build)
    monkeypatch.setattr(
        "ow_chat_logger.analysis.extract_chat_debug_data",
        lambda image, ocr, ocr_profile=None, config_overrides=None: {
            "config": {
                "languages": list(ocr_profile.languages if ocr_profile is not None else []),
            },
            "cropped_rgb_image": image,
            "masks": {
                "team": np.zeros((1, 1), dtype=np.uint8),
                "all": np.zeros((1, 1), dtype=np.uint8),
            },
            "raw_lines": {"team": [], "all": []},
        },
    )

    args = MagicMock(
        image=str(image_path),
        output_dir=str(tmp_dir / "out"),
        config=str(config_path),
    )
    run_analyze(args)

    assert created == {"languages": ["de"]}


def test_run_analyze_report_matches_existing_regression_expectation(monkeypatch, local_tmp_dir):
    tmp_dir = local_tmp_dir("analyze-regression")
    fixture_path = tmp_dir / "fixture.png"
    fixture_path.write_bytes(b"placeholder")
    expected_path = (
        Path(__file__).resolve().parent / "fixtures" / "regression" / "example_01.expected.json"
    )
    expected = json.loads(expected_path.read_text(encoding="utf-8"))

    monkeypatch.setattr(
        "ow_chat_logger.analysis.load_rgb_image",
        lambda path: np.zeros((1, 1, 3), dtype=np.uint8),
    )
    monkeypatch.setattr("ow_chat_logger.analysis.resolve_ocr_profile", lambda *args, **kwargs: _fake_profile())
    monkeypatch.setattr("ow_chat_logger.analysis.build_ocr_backend", lambda *args, **kwargs: object())
    monkeypatch.setattr(
        "ow_chat_logger.analysis.extract_chat_debug_data",
        lambda image, ocr, ocr_profile=None, config_overrides=None: {
            "config": {},
            "cropped_rgb_image": image,
            "masks": {
                "team": np.zeros((1, 1), dtype=np.uint8),
                "all": np.zeros((1, 1), dtype=np.uint8),
            },
            "raw_lines": {
                "team": ["[FrankShoe] : gg team no heals"],
                "all": [
                    "[Smokeelite3] : lads what the hell are yous doing",
                    "[Smokeelite3] : that was embarrasing",
                    "[MrHenderson] : you guys suck baalls",
                ],
            },
        },
    )

    output_dir = tmp_dir / "analysis"
    args = MagicMock(image=str(fixture_path), output_dir=str(output_dir), config=None)
    run_analyze(args)

    report = json.loads((output_dir / "report.json").read_text(encoding="utf-8"))
    assert report["final_lines"] == expected
