import json
from pathlib import Path
from unittest.mock import MagicMock

import numpy as np

from ow_chat_logger.analysis import run_analyze


def test_run_analyze_writes_report_and_masks(monkeypatch, local_tmp_dir):
    tmp_dir = local_tmp_dir("analyze-artifacts")
    output_dir = tmp_dir / "analysis"
    image_path = tmp_dir / "sample.png"
    image_path.write_bytes(b"placeholder")
    rgb_image = np.zeros((2, 2, 3), dtype=np.uint8)

    monkeypatch.setattr("ow_chat_logger.analysis.load_rgb_image", lambda path: rgb_image)
    monkeypatch.setattr("ow_chat_logger.analysis.OCREngine", lambda *args, **kwargs: object())
    monkeypatch.setattr(
        "ow_chat_logger.analysis.extract_chat_debug_data",
        lambda image, ocr, config_overrides=None: {
            "config": {
                "languages": ["en"],
                "confidence_threshold": 0.7,
                "text_threshold": 0.5,
                "scale_factor": 3,
                "y_merge_threshold": 18,
                "team_hsv_lower": [1, 2, 3],
                "team_hsv_upper": [4, 5, 6],
                "all_hsv_lower": [7, 8, 9],
                "all_hsv_upper": [10, 11, 12],
                "use_gpu": False,
            },
            "cropped_rgb_image": rgb_image,
            "masks": {
                "team": np.zeros((2, 2), dtype=np.uint8),
                "all": np.ones((2, 2), dtype=np.uint8),
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
    assert report["final_lines"] == {
        "team_lines": ["[Alice]: hi there"],
        "all_lines": ["[Bob]: hello"],
    }
    assert Path(report["artifacts"]["original_image"]).is_file()
    assert Path(report["artifacts"]["team_mask"]).is_file()
    assert Path(report["artifacts"]["all_mask"]).is_file()


def test_run_analyze_honors_json_overrides(monkeypatch, local_tmp_dir):
    tmp_dir = local_tmp_dir("analyze-overrides")
    image_path = tmp_dir / "sample.png"
    image_path.write_bytes(b"placeholder")
    config_path = tmp_dir / "override.json"
    config_path.write_text(
        json.dumps(
            {
                "languages": ["de"],
                "confidence_threshold": 0.25,
                "text_threshold": 0.33,
                "use_gpu": False,
            }
        ),
        encoding="utf-8",
    )

    created = {}
    monkeypatch.setattr(
        "ow_chat_logger.analysis.load_rgb_image",
        lambda path: np.zeros((1, 1, 3), dtype=np.uint8),
    )

    def fake_ocr(languages, confidence_threshold, text_threshold, use_gpu=True):
        created["languages"] = languages
        created["confidence_threshold"] = confidence_threshold
        created["text_threshold"] = text_threshold
        created["use_gpu"] = use_gpu
        return object()

    monkeypatch.setattr("ow_chat_logger.analysis.OCREngine", fake_ocr)
    monkeypatch.setattr(
        "ow_chat_logger.analysis.extract_chat_debug_data",
        lambda image, ocr, config_overrides=None: {
            "config": {**config_overrides},
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

    assert created == {
        "languages": ["de"],
        "confidence_threshold": 0.25,
        "text_threshold": 0.33,
        "use_gpu": False,
    }


def test_run_analyze_report_matches_existing_regression_expectation(monkeypatch, local_tmp_dir):
    tmp_dir = local_tmp_dir("analyze-regression")
    fixture_path = tmp_dir / "fixture.png"
    fixture_path.write_bytes(b"placeholder")
    expected_path = (
        Path(__file__).resolve().parent / "fixtures" / "regression" / "example_1.expected.json"
    )
    expected = json.loads(expected_path.read_text(encoding="utf-8"))

    monkeypatch.setattr(
        "ow_chat_logger.analysis.load_rgb_image",
        lambda path: np.zeros((1, 1, 3), dtype=np.uint8),
    )
    monkeypatch.setattr("ow_chat_logger.analysis.OCREngine", lambda *args, **kwargs: object())
    monkeypatch.setattr(
        "ow_chat_logger.analysis.extract_chat_debug_data",
        lambda image, ocr, config_overrides=None: {
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
                    "[Smokeelite3] : that was embarassing",
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
