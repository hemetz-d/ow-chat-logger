from __future__ import annotations

import csv
import json
import math
import re
from pathlib import Path
from typing import Any

from ow_chat_logger.analysis import load_json_file, load_rgb_image
from ow_chat_logger.config import (
    EASYOCR_MASTER_BASELINE_PROFILE,
    TESSERACT_DEFAULT_PROFILE,
    ResolvedOCRProfile,
    merge_runtime_config,
    resolve_ocr_profile,
)
from ow_chat_logger.message_processing import collect_screenshot_messages
from ow_chat_logger.ocr import OCRBackendUnavailableError, build_ocr_backend
from ow_chat_logger.pipeline import extract_chat_debug_data

_SPACE_RE = re.compile(r"\s+")


def default_fixture_dir() -> Path:
    return Path("tests") / "fixtures" / "regression"


def default_profile_names(config: dict[str, Any]) -> list[str]:
    candidates = [
        resolve_ocr_profile(config).name,
        EASYOCR_MASTER_BASELINE_PROFILE,
        TESSERACT_DEFAULT_PROFILE,
    ]
    out: list[str] = []
    for candidate in candidates:
        if candidate in config["ocr"]["profiles"] and candidate not in out:
            out.append(candidate)
    return out


def discover_benchmark_cases(fixture_dir: Path) -> list[tuple[Path, Path]]:
    if not fixture_dir.is_dir():
        return []
    out: list[tuple[Path, Path]] = []
    for png_path in sorted(fixture_dir.glob("*.png")):
        expected_path = fixture_dir / f"{png_path.stem}.expected.json"
        if expected_path.is_file():
            out.append((png_path, expected_path))
    return out


def _norm_line(value: str) -> str:
    return _SPACE_RE.sub(" ", value.strip())


def _norm_lines(lines: list[str]) -> list[str]:
    return [_norm_line(line) for line in lines]


def _channel_diff(actual_lines: list[str], expected_lines: list[str]) -> dict[str, Any]:
    norm_actual = _norm_lines(actual_lines)
    norm_expected = _norm_lines(expected_lines)
    return {
        "actual": norm_actual,
        "expected": norm_expected,
        "missing": [line for line in norm_expected if line not in norm_actual],
        "unexpected": [line for line in norm_actual if line not in norm_expected],
        "exact_match": norm_actual == norm_expected,
    }


def _percentile_ms(samples: list[float], percentile: float) -> float | None:
    if not samples:
        return None
    ordered = sorted(samples)
    index = max(0, min(len(ordered) - 1, math.ceil(percentile * len(ordered)) - 1))
    return ordered[index]


def _benchmark_case(
    *,
    png_path: Path,
    expected_path: Path,
    profile: ResolvedOCRProfile,
    backend,
) -> dict[str, Any]:
    expected = load_json_file(expected_path)
    rgb_image = load_rgb_image(png_path)
    sample_overrides = expected.get("config_overrides") or {}
    debug_data = extract_chat_debug_data(
        rgb_image,
        backend,
        config_overrides=sample_overrides,
        ocr_profile=profile,
    )
    actual_lines = collect_screenshot_messages(
        debug_data["raw_lines"],
        line_ys_by_channel=debug_data.get("raw_line_ys"),
        raw_line_prefix_evidence_by_channel=debug_data.get("raw_line_prefix_evidence"),
        raw_continuation_y_gaps=debug_data.get("raw_continuation_y_gaps"),
    )
    team_diff = _channel_diff(actual_lines["team_lines"], list(expected.get("team_lines") or []))
    all_diff = _channel_diff(actual_lines["all_lines"], list(expected.get("all_lines") or []))
    timings = debug_data["timings"]

    return {
        "fixture_name": png_path.name,
        "fixture_path": str(png_path.resolve()),
        "expected_path": str(expected_path.resolve()),
        "ocr_profile": profile.name,
        "ocr_engine": profile.engine_id,
        "status": "ok",
        "exact_match": team_diff["exact_match"] and all_diff["exact_match"],
        "team": team_diff,
        "all": all_diff,
        "timings": {
            "preprocess_ms": timings["preprocess_seconds"] * 1000.0,
            "ocr_ms": timings["ocr_seconds"] * 1000.0,
            "parse_ms": timings["parse_seconds"] * 1000.0,
            "total_ms": (
                timings["preprocess_seconds"] + timings["ocr_seconds"] + timings["parse_seconds"]
            )
            * 1000.0,
        },
    }


def _unavailable_case(
    *,
    png_path: Path,
    expected_path: Path,
    profile_name: str,
    engine_id: str,
    message: str,
) -> dict[str, Any]:
    return {
        "fixture_name": png_path.name,
        "fixture_path": str(png_path.resolve()),
        "expected_path": str(expected_path.resolve()),
        "ocr_profile": profile_name,
        "ocr_engine": engine_id,
        "status": "unavailable",
        "error": message,
        "exact_match": False,
        "team": {
            "actual": [],
            "expected": [],
            "missing": [],
            "unexpected": [],
            "exact_match": False,
        },
        "all": {
            "actual": [],
            "expected": [],
            "missing": [],
            "unexpected": [],
            "exact_match": False,
        },
        "timings": {"preprocess_ms": None, "ocr_ms": None, "parse_ms": None, "total_ms": None},
    }


def summarize_benchmark_results(rows: list[dict[str, Any]]) -> dict[str, Any]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        grouped.setdefault(row["ocr_profile"], []).append(row)

    summary: dict[str, Any] = {}
    ranking: list[dict[str, Any]] = []
    for profile_name, profile_rows in grouped.items():
        ok_rows = [row for row in profile_rows if row["status"] == "ok"]
        exact_passes = sum(1 for row in ok_rows if row["exact_match"])
        total_ms = [
            row["timings"]["total_ms"] for row in ok_rows if row["timings"]["total_ms"] is not None
        ]
        unavailable = sum(1 for row in profile_rows if row["status"] == "unavailable")
        errors = sum(1 for row in profile_rows if row["status"] == "error")
        pass_rate = (exact_passes / len(ok_rows)) if ok_rows else 0.0
        profile_summary = {
            "ocr_engine": profile_rows[0]["ocr_engine"] if profile_rows else "",
            "cases_total": len(profile_rows),
            "cases_ran": len(ok_rows),
            "exact_passes": exact_passes,
            "exact_pass_rate": pass_rate,
            "unavailable_cases": unavailable,
            "error_cases": errors,
            "total_ms_p50": _percentile_ms(total_ms, 0.50),
            "total_ms_p95": _percentile_ms(total_ms, 0.95),
        }
        summary[profile_name] = profile_summary
        ranking.append({"ocr_profile": profile_name, **profile_summary})

    ranking.sort(
        key=lambda row: (
            -float(row["exact_pass_rate"]),
            float("inf") if row["total_ms_p50"] is None else float(row["total_ms_p50"]),
            row["ocr_profile"],
        )
    )
    return {"profiles": summary, "ranking": ranking}


def write_benchmark_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "fixture_name",
                "ocr_profile",
                "ocr_engine",
                "status",
                "exact_match",
                "preprocess_ms",
                "ocr_ms",
                "parse_ms",
                "total_ms",
                "team_missing",
                "team_unexpected",
                "all_missing",
                "all_unexpected",
                "error",
            ],
        )
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    "fixture_name": row["fixture_name"],
                    "ocr_profile": row["ocr_profile"],
                    "ocr_engine": row["ocr_engine"],
                    "status": row["status"],
                    "exact_match": row["exact_match"],
                    "preprocess_ms": row["timings"]["preprocess_ms"],
                    "ocr_ms": row["timings"]["ocr_ms"],
                    "parse_ms": row["timings"]["parse_ms"],
                    "total_ms": row["timings"]["total_ms"],
                    "team_missing": json.dumps(row["team"]["missing"]),
                    "team_unexpected": json.dumps(row["team"]["unexpected"]),
                    "all_missing": json.dumps(row["all"]["missing"]),
                    "all_unexpected": json.dumps(row["all"]["unexpected"]),
                    "error": row.get("error", ""),
                }
            )


def print_benchmark_summary(summary: dict[str, Any]) -> None:
    ranking = summary["ranking"]
    if not ranking:
        print("No benchmark results to summarize.")
        return
    print("OCR benchmark summary:")
    for row in ranking:
        p50 = row["total_ms_p50"]
        p50_display = "-" if p50 is None else f"{p50:.2f} ms"
        print(
            f"  {row['ocr_profile']} ({row['ocr_engine']}): "
            f"{row['exact_passes']}/{row['cases_ran']} exact matches, p50 total {p50_display}"
        )


def run_benchmark(args) -> int:
    config_overrides = load_json_file(Path(args.benchmark_config)) if args.benchmark_config else {}
    config = merge_runtime_config(config_overrides)
    fixture_dir = Path(args.fixtures) if args.fixtures else default_fixture_dir()
    cases = discover_benchmark_cases(fixture_dir)
    if not cases:
        print(f"No benchmark fixtures found in {fixture_dir}.")
        return 0

    profile_names = list(args.profiles) if args.profiles else default_profile_names(config)
    rows: list[dict[str, Any]] = []

    for profile_name in profile_names:
        profile = resolve_ocr_profile(config, profile_name)
        try:
            backend = build_ocr_backend(profile)
        except OCRBackendUnavailableError as exc:
            rows.extend(
                [
                    _unavailable_case(
                        png_path=png_path,
                        expected_path=expected_path,
                        profile_name=profile.name,
                        engine_id=profile.engine_id,
                        message=str(exc),
                    )
                    for png_path, expected_path in cases
                ]
            )
            continue

        for png_path, expected_path in cases:
            try:
                rows.append(
                    _benchmark_case(
                        png_path=png_path,
                        expected_path=expected_path,
                        profile=profile,
                        backend=backend,
                    )
                )
            except Exception as exc:
                rows.append(
                    {
                        "fixture_name": png_path.name,
                        "fixture_path": str(png_path.resolve()),
                        "expected_path": str(expected_path.resolve()),
                        "ocr_profile": profile.name,
                        "ocr_engine": profile.engine_id,
                        "status": "error",
                        "error": str(exc),
                        "exact_match": False,
                        "team": {
                            "actual": [],
                            "expected": [],
                            "missing": [],
                            "unexpected": [],
                            "exact_match": False,
                        },
                        "all": {
                            "actual": [],
                            "expected": [],
                            "missing": [],
                            "unexpected": [],
                            "exact_match": False,
                        },
                        "timings": {
                            "preprocess_ms": None,
                            "ocr_ms": None,
                            "parse_ms": None,
                            "total_ms": None,
                        },
                    }
                )

    summary = summarize_benchmark_results(rows)
    report = {
        "fixture_dir": str(fixture_dir.resolve()),
        "profiles": profile_names,
        "results": rows,
        "summary": summary,
    }

    if args.json_out:
        json_path = Path(args.json_out)
        json_path.parent.mkdir(parents=True, exist_ok=True)
        json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    if args.csv_out:
        write_benchmark_csv(Path(args.csv_out), rows)

    print_benchmark_summary(summary)
    return 0
