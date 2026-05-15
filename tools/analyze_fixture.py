"""Deep-dive analysis of a single regression fixture.

Runs the same pipeline as `tests/test_regression_screenshots.py` for one
fixture (looked up by stem name) and prints a detailed breakdown:

  - effective config + mask stats
  - actual vs expected diff per channel
  - per-raw-line trace: classification + prefix-evidence gate breakdown
  - writes original / team_mask / all_mask / fixture_report.json artifacts to disk

Usage:
    python tools/analyze_fixture.py example_14
    python tools/analyze_fixture.py example_14 --channel team
    python tools/analyze_fixture.py example_14 --output-dir ./tmp/ex14
    python tools/analyze_fixture.py example_14 --no-masks
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

import numpy as np

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

from ow_chat_logger.analysis import load_rgb_image, write_analysis_artifacts  # noqa: E402
from ow_chat_logger.config import resolve_ocr_profile  # noqa: E402
from ow_chat_logger.message_processing import collect_screenshot_messages  # noqa: E402
from ow_chat_logger.ocr import build_ocr_backend  # noqa: E402
from ow_chat_logger.parser import classify_line  # noqa: E402
from ow_chat_logger.pipeline import extract_chat_debug_data  # noqa: E402

FIXTURE_DIR = REPO_ROOT / "tests" / "fixtures" / "regression"


def _norm_line(s: str) -> str:
    return re.sub(r"\s+", " ", s.strip())


def _diff_lines(actual: list[str], expected: list[str]) -> tuple[list[str], list[str], list[str]]:
    norm_actual = [_norm_line(line) for line in actual]
    norm_expected = [_norm_line(line) for line in expected]
    missing = [line for line in norm_expected if line not in norm_actual]
    unexpected = [line for line in norm_actual if line not in norm_expected]
    matched = [line for line in norm_expected if line in norm_actual]
    return missing, unexpected, matched


def _format_lines(lines: list[str]) -> str:
    return "\n".join(f"  - {line}" for line in lines) if lines else "  <none>"


def _print_header(title: str) -> None:
    print()
    print(f"== {title} ==")


def _print_config(debug_data: dict[str, Any]) -> None:
    config = debug_data.get("config") or {}
    _print_header("Effective config")
    for key in (
        "scale_factor",
        "high_quality_ocr",
        "y_merge_threshold",
        "max_continuation_y_gap_factor",
        "missing_prefix_body_start_tolerance",
        "min_box_height_fraction",
        "team_hsv_lower",
        "team_hsv_upper",
        "all_hsv_lower",
        "all_hsv_upper",
    ):
        if key in config:
            print(f"  {key}: {config[key]}")


def _print_mask_stats(debug_data: dict[str, Any]) -> None:
    masks = debug_data.get("masks") or {}
    _print_header("Mask stats")
    for channel in ("team", "all"):
        mask = masks.get(channel)
        nonzero = int(np.count_nonzero(mask)) if mask is not None else 0
        ocr_skipped = bool((debug_data.get("ocr_skipped") or {}).get(channel, False))
        print(f"  {channel}: {nonzero:,} nonzero pixels (ocr_skipped={ocr_skipped})")


def _print_channel_diff(channel: str, actual: list[str], expected: list[str]) -> bool:
    missing, unexpected, matched = _diff_lines(actual, expected)
    passed = not missing and not unexpected
    _print_header(f"{channel.upper()} CHANNEL - {'PASS' if passed else 'FAIL'}")
    print(f"Expected ({len(expected)} lines):")
    print(_format_lines([_norm_line(line) for line in expected]))
    print(f"Actual ({len(actual)} lines):")
    print(_format_lines([_norm_line(line) for line in actual]))
    if not passed:
        print(f"Missing ({len(missing)}):")
        print(_format_lines(missing))
        print(f"Unexpected ({len(unexpected)}):")
        print(_format_lines(unexpected))
        print(f"Matched: {len(matched)} of {len(expected)}")
    return passed


def _format_prefix_evidence(evidence: dict[str, Any]) -> str:
    if not evidence:
        return "      (no prefix-evidence data)"
    lines: list[str] = []
    lines.append(
        "      has_missing_prefix_evidence="
        f"{evidence.get('has_missing_prefix_evidence')}"
        f"  recovered_player={evidence.get('recovered_player')!r}"
    )
    lines.append(
        "      anchor_count="
        f"{evidence.get('anchor_count')}"
        f"  body_start_range={evidence.get('body_start_range')}"
        f"  first_box_x={evidence.get('first_box_x')}"
    )
    lines.append(
        f"      within_body_start_range={evidence.get('within_body_start_range')}"
        f"  within_line_height_range={evidence.get('within_line_height_range')}"
        f"  line_height_ratio={evidence.get('line_height_ratio')}"
    )
    lines.append(
        f"      probe_nonzero={evidence.get('probe_nonzero_pixels')}"
        f"  probe_density={evidence.get('probe_density')}"
        f"  probe_largest_component_fraction="
        f"{evidence.get('probe_largest_component_fraction')}"
    )
    return "\n".join(lines)


def _print_channel_trace(channel: str, debug_data: dict[str, Any], show_prefix_gates: bool) -> None:
    raw_lines = (debug_data.get("raw_lines") or {}).get(channel) or []
    raw_ys = (debug_data.get("raw_line_ys") or {}).get(channel) or [None] * len(raw_lines)
    raw_evidence = (debug_data.get("raw_line_prefix_evidence") or {}).get(channel) or []
    layout = (debug_data.get("raw_channel_layouts") or {}).get(channel) or {}

    _print_header(f"{channel.upper()} per-line trace")
    print(
        f"  layout: anchor_count={layout.get('anchor_count')}"
        f"  anchor_players={layout.get('anchor_players')}"
        f"  body_start_range={layout.get('body_start_range')}"
    )

    if not raw_lines:
        print("  <no raw lines>")
        return

    for idx, line in enumerate(raw_lines):
        y = raw_ys[idx] if idx < len(raw_ys) else None
        classification = classify_line(line)
        category = classification.get("category")
        details = ""
        if category in {"standard", "hero"}:
            details = f" player={classification.get('player')!r} msg={classification.get('msg')!r}"
            if classification.get("ocr_fix_closing_bracket"):
                details += " ocr_fix_closing_bracket=True"
        elif category == "continuation":
            details = f" text={classification.get('msg')!r}"
        else:
            details = f" msg={classification.get('msg', '')!r}"

        print(f"  [{idx}] y={y} raw={line!r}")
        print(f"      classify: {category}{details}")
        if show_prefix_gates and idx < len(raw_evidence):
            print(_format_prefix_evidence(raw_evidence[idx]))


def _write_artifacts(
    debug_data: dict[str, Any],
    actual: dict[str, list[str]],
    expected: dict[str, Any],
    output_dir: Path,
    write_masks: bool,
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    artifacts: dict[str, Any] = {}

    if write_masks:
        cropped = debug_data.get("cropped_rgb_image")
        if cropped is not None:
            written = write_analysis_artifacts(cropped, debug_data, output_dir)
            written.pop(
                "report", None
            )  # write_analysis_artifacts lists this path but does not write it
            artifacts.update(written)

    report = {
        "expected": {
            "team_lines": expected.get("team_lines") or [],
            "all_lines": expected.get("all_lines") or [],
        },
        "actual": actual,
        "config": debug_data.get("config"),
        "ocr_skipped": debug_data.get("ocr_skipped"),
        "raw_lines": debug_data.get("raw_lines"),
        "raw_line_ys": debug_data.get("raw_line_ys"),
        "raw_channel_layouts": debug_data.get("raw_channel_layouts"),
        "raw_line_prefix_evidence": debug_data.get("raw_line_prefix_evidence"),
        "raw_continuation_y_gaps": debug_data.get("raw_continuation_y_gaps"),
    }
    report_path = output_dir / "fixture_report.json"
    report_path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    artifacts["fixture_report"] = str(report_path)
    return artifacts


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("fixture", help="Fixture stem name, e.g. example_14")
    parser.add_argument(
        "--channel",
        choices=("team", "all", "both"),
        default="both",
        help="Restrict the per-line trace to one channel (default: both).",
    )
    parser.add_argument(
        "--output-dir",
        help="Where to write report.json + mask PNGs (default: ./tmp/analyze_<fixture>).",
    )
    parser.add_argument(
        "--no-masks",
        action="store_true",
        help="Skip writing original.png / *_mask.png to disk.",
    )
    parser.add_argument(
        "--no-trace",
        action="store_true",
        help="Skip the per-raw-line classification trace.",
    )
    parser.add_argument(
        "--no-prefix-gates",
        action="store_true",
        help="Omit prefix-evidence gate breakdown from the trace.",
    )
    args = parser.parse_args()

    fixture_stem = args.fixture
    png_path = FIXTURE_DIR / f"{fixture_stem}.png"
    expected_path = FIXTURE_DIR / f"{fixture_stem}.expected.json"
    if not png_path.is_file():
        print(f"error: fixture image not found: {png_path}", file=sys.stderr)
        return 2
    if not expected_path.is_file():
        print(f"error: expected JSON not found: {expected_path}", file=sys.stderr)
        return 2

    output_dir = (
        Path(args.output_dir) if args.output_dir else REPO_ROOT / "tmp" / f"analyze_{fixture_stem}"
    )

    expected = json.loads(expected_path.read_text(encoding="utf-8"))
    overrides = expected.get("config_overrides") or {}
    profile = resolve_ocr_profile()
    ocr = build_ocr_backend(profile)

    rgb = load_rgb_image(png_path)
    debug_data = extract_chat_debug_data(
        rgb,
        ocr,
        config_overrides=overrides,
        ocr_profile=profile,
    )
    actual = collect_screenshot_messages(
        debug_data["raw_lines"],
        line_ys_by_channel=debug_data.get("raw_line_ys"),
        raw_line_prefix_evidence_by_channel=debug_data.get("raw_line_prefix_evidence"),
        raw_continuation_y_gaps=debug_data.get("raw_continuation_y_gaps"),
    )

    print(f"=== {fixture_stem} ===")
    print(f"Image: {png_path}")
    print(f"Profile: {profile.name} (engine={profile.engine_id})")

    _print_config(debug_data)
    _print_mask_stats(debug_data)

    team_pass = _print_channel_diff(
        "team", actual.get("team_lines") or [], expected.get("team_lines") or []
    )
    all_pass = _print_channel_diff(
        "all", actual.get("all_lines") or [], expected.get("all_lines") or []
    )

    if not args.no_trace:
        channels = ("team", "all") if args.channel == "both" else (args.channel,)
        for channel in channels:
            _print_channel_trace(channel, debug_data, show_prefix_gates=not args.no_prefix_gates)

    artifacts = _write_artifacts(
        debug_data, actual, expected, output_dir, write_masks=not args.no_masks
    )
    _print_header("Artifacts")
    for name, path in artifacts.items():
        if isinstance(path, dict):
            counts = ", ".join(f"{ch}={len(paths)}" for ch, paths in path.items())
            print(f"  {name}: {counts} (under {output_dir})")
        else:
            print(f"  {name}: {path}")

    return 0 if (team_pass and all_pass) else 1


if __name__ == "__main__":
    raise SystemExit(main())
