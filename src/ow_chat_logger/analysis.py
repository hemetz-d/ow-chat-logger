from __future__ import annotations

import datetime
import json
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from ow_chat_logger.config import CONFIG, get_app_paths
from ow_chat_logger.message_processing import collect_screenshot_messages
from ow_chat_logger.ocr_engine import OCREngine
from ow_chat_logger.pipeline import extract_chat_debug_data

DISPLAY_CONFIG_KEYS = (
    "languages",
    "confidence_threshold",
    "text_threshold",
    "scale_factor",
    "y_merge_threshold",
    "team_hsv_lower",
    "team_hsv_upper",
    "all_hsv_lower",
    "all_hsv_upper",
    "use_gpu",
)


def load_json_file(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Expected JSON object in {path}")
    return data


def load_rgb_image(path: Path) -> np.ndarray:
    bgr = cv2.imread(str(path))
    if bgr is None:
        raise FileNotFoundError(f"Could not read image: {path}")
    return cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)


def default_analysis_output_dir() -> Path:
    timestamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    return get_app_paths().log_dir / "analysis" / timestamp


def analysis_report_paths(output_dir: Path) -> dict[str, Path]:
    return {
        "original_image": output_dir / "original.png",
        "team_mask": output_dir / "team_mask.png",
        "all_mask": output_dir / "all_mask.png",
        "report": output_dir / "report.json",
    }


def write_analysis_artifacts(
    analyzed_rgb_image: np.ndarray,
    debug_data: dict[str, Any],
    output_dir: Path,
) -> dict[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    paths = analysis_report_paths(output_dir)

    cv2.imwrite(
        str(paths["original_image"]),
        cv2.cvtColor(analyzed_rgb_image, cv2.COLOR_RGB2BGR),
    )
    cv2.imwrite(str(paths["team_mask"]), debug_data["masks"]["team"])
    cv2.imwrite(str(paths["all_mask"]), debug_data["masks"]["all"])

    return {key: str(path) for key, path in paths.items()}


def print_analysis_summary(report: dict[str, Any], output_dir: Path) -> None:
    print(f"Analysis artifacts written to: {output_dir}")
    print("Effective OCR config:")
    for key in DISPLAY_CONFIG_KEYS:
        if key in report["effective_config"]:
            print(f"  {key}: {report['effective_config'][key]}")

    print("Final team lines:")
    if report["final_lines"]["team_lines"]:
        for line in report["final_lines"]["team_lines"]:
            print(f"  {line}")
    else:
        print("  <none>")

    print("Final all lines:")
    if report["final_lines"]["all_lines"]:
        for line in report["final_lines"]["all_lines"]:
            print(f"  {line}")
    else:
        print("  <none>")


def run_analyze(args) -> int:
    image_path = Path(args.image)
    output_dir = Path(args.output_dir) if args.output_dir else default_analysis_output_dir()
    overrides = load_json_file(Path(args.config)) if args.config else {}

    effective_config = {**CONFIG, **overrides}
    ocr = OCREngine(
        effective_config["languages"],
        effective_config["confidence_threshold"],
        effective_config["text_threshold"],
        use_gpu=effective_config.get("use_gpu", True),
    )

    rgb_image = load_rgb_image(image_path)
    debug_data = extract_chat_debug_data(
        rgb_image,
        ocr,
        config_overrides=overrides,
    )
    final_lines = collect_screenshot_messages(debug_data["raw_lines"])
    report = {
        "source_image": str(image_path.resolve()),
        "effective_config": debug_data["config"],
        "raw_lines": debug_data["raw_lines"],
        "final_lines": final_lines,
    }
    report["artifacts"] = write_analysis_artifacts(
        debug_data["cropped_rgb_image"],
        debug_data,
        output_dir,
    )
    Path(report["artifacts"]["report"]).write_text(
        json.dumps(report, indent=2),
        encoding="utf-8",
    )
    print_analysis_summary(report, output_dir)
    return 0
