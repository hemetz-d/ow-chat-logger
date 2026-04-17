import csv
import json
from argparse import Namespace

import numpy as np

from ow_chat_logger.benchmark import (
    default_profile_names,
    discover_benchmark_cases,
    run_benchmark,
    summarize_benchmark_results,
)
from ow_chat_logger.ocr import OCRBackendUnavailableError


def test_default_profile_names_include_builtin_comparison_set():
    config = {
        "ocr": {
            "default_profile": "windows_default",
            "profiles": {
                "windows_default": {},
                "easyocr_master_baseline": {},
                "tesseract_default": {},
            },
        }
    }

    assert default_profile_names(config) == [
        "windows_default",
        "easyocr_master_baseline",
        "tesseract_default",
    ]


def test_discover_benchmark_cases_pairs_png_with_expected_json(local_tmp_dir):
    tmp_dir = local_tmp_dir("benchmark-cases")
    (tmp_dir / "sample.png").write_bytes(b"png")
    (tmp_dir / "sample.expected.json").write_text("{}", encoding="utf-8")
    (tmp_dir / "ignored.png").write_bytes(b"png")

    cases = discover_benchmark_cases(tmp_dir)

    assert cases == [(tmp_dir / "sample.png", tmp_dir / "sample.expected.json")]


def test_summarize_benchmark_results_ranks_by_pass_rate_then_latency():
    rows = [
        {
            "ocr_profile": "windows_default",
            "ocr_engine": "windows",
            "status": "ok",
            "exact_match": True,
            "timings": {"total_ms": 10.0},
        },
        {
            "ocr_profile": "easyocr_master_baseline",
            "ocr_engine": "easyocr",
            "status": "ok",
            "exact_match": True,
            "timings": {"total_ms": 20.0},
        },
        {
            "ocr_profile": "easyocr_master_baseline",
            "ocr_engine": "easyocr",
            "status": "ok",
            "exact_match": False,
            "timings": {"total_ms": 30.0},
        },
    ]

    summary = summarize_benchmark_results(rows)

    assert summary["ranking"][0]["ocr_profile"] == "windows_default"
    assert summary["profiles"]["windows_default"]["exact_pass_rate"] == 1.0
    assert summary["profiles"]["easyocr_master_baseline"]["exact_pass_rate"] == 0.5


def test_summarize_benchmark_results_keeps_percentiles_in_ms_units():
    rows = [
        {
            "ocr_profile": "windows_default",
            "ocr_engine": "windows",
            "status": "ok",
            "exact_match": True,
            "timings": {"total_ms": 120.0},
        },
        {
            "ocr_profile": "windows_default",
            "ocr_engine": "windows",
            "status": "ok",
            "exact_match": True,
            "timings": {"total_ms": 150.0},
        },
    ]

    summary = summarize_benchmark_results(rows)

    assert summary["profiles"]["windows_default"]["total_ms_p50"] == 120.0
    assert summary["profiles"]["windows_default"]["total_ms_p95"] == 150.0


def test_run_benchmark_writes_json_and_csv_reports(monkeypatch, local_tmp_dir):
    fixture_dir = local_tmp_dir("benchmark-fixtures")
    png_path = fixture_dir / "fixture.png"
    expected_path = fixture_dir / "fixture.expected.json"
    png_path.write_bytes(b"fake")
    expected_path.write_text(
        json.dumps({"team_lines": ["[Alice]: hi"], "all_lines": []}),
        encoding="utf-8",
    )

    monkeypatch.setattr("ow_chat_logger.benchmark.load_rgb_image", lambda path: np.zeros((2, 2, 3), dtype=np.uint8))
    monkeypatch.setattr("ow_chat_logger.benchmark.build_ocr_backend", lambda profile: object())
    monkeypatch.setattr(
        "ow_chat_logger.benchmark.extract_chat_debug_data",
        lambda rgb_image, backend, config_overrides=None, ocr_profile=None: {
            "raw_lines": {"team": ["[Alice] : hi"], "all": []},
            "timings": {
                "preprocess_seconds": 0.001,
                "ocr_seconds": 0.002,
                "parse_seconds": 0.003,
            },
        },
    )

    json_out = fixture_dir / "report.json"
    csv_out = fixture_dir / "report.csv"
    args = Namespace(
        fixtures=str(fixture_dir),
        profiles=["windows_default"],
        benchmark_config=None,
        json_out=str(json_out),
        csv_out=str(csv_out),
    )

    assert run_benchmark(args) == 0

    report = json.loads(json_out.read_text(encoding="utf-8"))
    assert report["summary"]["profiles"]["windows_default"]["exact_passes"] == 1
    rows = list(csv.DictReader(csv_out.open("r", encoding="utf-8")))
    assert rows[0]["ocr_profile"] == "windows_default"
    assert rows[0]["status"] == "ok"


def test_run_benchmark_resolves_profile_once_per_profile(monkeypatch, local_tmp_dir):
    fixture_dir = local_tmp_dir("benchmark-resolve-once")
    expected_payload = json.dumps({"team_lines": [], "all_lines": []})
    for stem in ("a", "b", "c"):
        (fixture_dir / f"{stem}.png").write_bytes(b"fake")
        (fixture_dir / f"{stem}.expected.json").write_text(expected_payload, encoding="utf-8")

    import ow_chat_logger.benchmark as benchmark_mod

    real_resolve = benchmark_mod.resolve_ocr_profile
    call_counts: dict[str, int] = {}

    def counting_resolve(config=None, profile_name=None):
        call_counts[profile_name or "<default>"] = call_counts.get(profile_name or "<default>", 0) + 1
        return real_resolve(config, profile_name)

    monkeypatch.setattr(benchmark_mod, "resolve_ocr_profile", counting_resolve)
    monkeypatch.setattr(benchmark_mod, "load_rgb_image", lambda path: np.zeros((2, 2, 3), dtype=np.uint8))
    monkeypatch.setattr(benchmark_mod, "build_ocr_backend", lambda profile: object())
    monkeypatch.setattr(
        benchmark_mod,
        "extract_chat_debug_data",
        lambda rgb_image, backend, config_overrides=None, ocr_profile=None: {
            "raw_lines": {"team": [], "all": []},
            "timings": {
                "preprocess_seconds": 0.0,
                "ocr_seconds": 0.0,
                "parse_seconds": 0.0,
            },
        },
    )

    args = Namespace(
        fixtures=str(fixture_dir),
        profiles=["windows_default"],
        benchmark_config=None,
        json_out=None,
        csv_out=None,
    )

    assert run_benchmark(args) == 0
    assert call_counts.get("windows_default") == 1


def test_run_benchmark_marks_unavailable_profiles(monkeypatch, local_tmp_dir):
    fixture_dir = local_tmp_dir("benchmark-unavailable")
    (fixture_dir / "fixture.png").write_bytes(b"fake")
    (fixture_dir / "fixture.expected.json").write_text(
        json.dumps({"team_lines": [], "all_lines": []}),
        encoding="utf-8",
    )

    def fake_build(profile):
        raise OCRBackendUnavailableError(f"{profile.name} missing")

    monkeypatch.setattr("ow_chat_logger.benchmark.build_ocr_backend", fake_build)

    args = Namespace(
        fixtures=str(fixture_dir),
        profiles=["easyocr_master_baseline"],
        benchmark_config=None,
        json_out=None,
        csv_out=None,
    )

    assert run_benchmark(args) == 0
