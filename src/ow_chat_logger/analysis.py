from __future__ import annotations

import datetime
import json
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from ow_chat_logger.config import get_app_paths, merge_runtime_config, resolve_ocr_profile
from ow_chat_logger.message_processing import collect_screenshot_messages
from ow_chat_logger.ocr import build_ocr_backend
from ow_chat_logger.pipeline import extract_chat_debug_data

DISPLAY_CONFIG_KEYS = (
    "languages",
    "scale_factor",
    "y_merge_threshold",
    "team_hsv_lower",
    "team_hsv_upper",
    "all_hsv_lower",
    "all_hsv_upper",
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


def _mask_step_output_paths(output_dir: Path, channel: str, steps: list[tuple[str, np.ndarray]]) -> list[Path]:
    return [output_dir / f"{channel}_{step_name}.png" for step_name, _ in steps]


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

    mask_debug_artifacts: dict[str, list[str]] = {}
    mask_debug_steps = debug_data.get("mask_debug_steps") or {}
    for channel in ("team", "all"):
        written_paths: list[str] = []
        channel_steps = list(mask_debug_steps.get(channel) or [])
        for path, (_, mask_image) in zip(
            _mask_step_output_paths(output_dir, channel, channel_steps),
            channel_steps,
        ):
            cv2.imwrite(str(path), mask_image)
            written_paths.append(str(path))
        mask_debug_artifacts[channel] = written_paths

    artifacts = {key: str(path) for key, path in paths.items()}
    artifacts["mask_debug_steps"] = mask_debug_artifacts
    return artifacts


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
    runtime_overrides = load_json_file(Path(args.config)) if args.config else {}
    profile_name = getattr(args, "ocr_profile", None)
    if not isinstance(profile_name, str):
        profile_name = None

    effective_config = merge_runtime_config(runtime_overrides)
    profile = resolve_ocr_profile(effective_config, profile_name)
    ocr = build_ocr_backend(profile)

    rgb_image = load_rgb_image(image_path)
    debug_data = extract_chat_debug_data(
        rgb_image,
        ocr,
        ocr_profile=profile,
    )
    final_lines = collect_screenshot_messages(debug_data["raw_lines"])
    report = {
        "source_image": str(image_path.resolve()),
        "effective_config": debug_data["config"],
        "ocr_profile": {
            "name": profile.name,
            "engine": profile.engine_id,
            "languages": profile.languages,
        },
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
