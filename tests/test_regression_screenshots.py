"""
Screenshot OCR regression: compare filtered screenshot extraction output to expected JSON.

Run (loads Windows OCR):
  pip install -e ".[dev]"
  pytest --run-ocr tests/test_regression_screenshots.py

Add pairs under tests/fixtures/regression/:
  my_chat.png
  my_chat.expected.json
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import cv2
import numpy as np
import pytest

from ow_chat_logger.message_processing import collect_screenshot_messages
from ow_chat_logger.pipeline import extract_chat_debug_data

pytestmark = pytest.mark.ocr

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "regression"

# Fixtures whose detection output does not yet match the expected JSON.
# Each entry has a per-fixture root-cause writeup in
# `tests/fixtures/regression/KNOWN_FAILURES.md`. The intent is to keep the
# currently-passing fixtures as a CI signal: a previously-passing fixture
# that regresses fails the build, while a known-failing fixture that gets
# fixed shows up as XPASS — visible without breaking CI.
#
# `strict=False` because some failures (ex_05, ex_13, ex_17, ex_27) are
# OCR-engine non-deterministic — they sometimes pass run-to-run. A strict
# xfail would oscillate between XFAIL and CI-failing XPASS for those.
#
# When fixing a fixture: remove its stem from this set in the same PR
# that resolves the underlying issue.
KNOWN_FAILURES: frozenset[str] = frozenset(
    {
        "example_04",
        "example_05",
        "example_09",
        "example_11",
        "example_12",
        "example_14",
        "example_18",
        "example_22",
        "example_23",
        "example_24",
        "example_25",
        "example_27",
        "example_28",
        "example_31",
    }
)


def _natural_sort_key(path: Path) -> list[int | str]:
    parts = re.split(r"(\d+)", path.stem)
    return [int(part) if part.isdigit() else part.lower() for part in parts]


def _load_rgb(path: Path) -> np.ndarray:
    bgr = cv2.imread(str(path))
    assert bgr is not None, f"could not read image: {path}"
    return cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)


def _norm_line(s: str) -> str:
    return re.sub(r"\s+", " ", s.strip())


def _norm_record(record: dict[str, str]) -> dict[str, str]:
    return {key: _norm_line(value) for key, value in record.items()}


def _format_line_list(lines: list[str]) -> str:
    if not lines:
        return "  <none>"
    return "\n".join(f"  - {line}" for line in lines)


def _assert_channel_lines_match(
    *,
    fixture_name: str,
    channel_name: str,
    actual_lines: list[str],
    expected_lines: list[str],
) -> None:
    norm_actual = [_norm_line(x) for x in actual_lines]
    norm_expected = [_norm_line(x) for x in expected_lines]
    if norm_actual == norm_expected:
        return

    missing = [line for line in norm_expected if line not in norm_actual]
    unexpected = [line for line in norm_actual if line not in norm_expected]

    pytest.fail(
        "\n".join(
            [
                f"{fixture_name} {channel_name} mismatch",
                "",
                "Expected:",
                _format_line_list(norm_expected),
                "",
                "Actual:",
                _format_line_list(norm_actual),
                "",
                "Missing:",
                _format_line_list(missing),
                "",
                "Unexpected:",
                _format_line_list(unexpected),
            ]
        ),
        pytrace=False,
    )


def _discover_cases() -> list[tuple[Path, Path]]:
    if not FIXTURE_DIR.is_dir():
        return []
    out: list[tuple[Path, Path]] = []
    for png in sorted(FIXTURE_DIR.glob("*.png"), key=_natural_sort_key):
        expected = FIXTURE_DIR / f"{png.stem}.expected.json"
        if expected.is_file():
            out.append((png, expected))
    return out


CASES = _discover_cases()


def _params():
    if not CASES:
        return [pytest.param(None, None, id="no-fixtures")]
    params = []
    for png, expected in CASES:
        marks = []
        if png.stem in KNOWN_FAILURES:
            marks.append(
                pytest.mark.xfail(
                    strict=False,
                    reason=f"known failure — see KNOWN_FAILURES.md::{png.stem}",
                )
            )
        params.append(pytest.param(png, expected, id=png.stem, marks=marks))
    return params


@pytest.mark.parametrize("png_path,expected_path", _params())
def test_screenshot_matches_expected(
    png_path: Path | None,
    expected_path: Path | None,
    request,
):
    if png_path is None or expected_path is None:
        pytest.skip(
            "Add screenshot pairs: tests/fixtures/regression/<name>.png + "
            "<name>.expected.json (see README in that folder).",
        )

    ocr_engine_session = request.getfixturevalue("ocr_engine_session")
    ocr_profile_session = request.getfixturevalue("ocr_profile_session")

    raw = expected_path.read_text(encoding="utf-8")
    expected = json.loads(raw)

    overrides = expected.get("config_overrides") or {}
    want_team = expected.get("team_lines")
    want_all = expected.get("all_lines")
    assert want_team is not None, f"{expected_path}: missing team_lines"
    assert want_all is not None, f"{expected_path}: missing all_lines"

    rgb = _load_rgb(png_path)
    debug_data = extract_chat_debug_data(
        rgb,
        ocr_engine_session,
        config_overrides=overrides,
        ocr_profile=ocr_profile_session,
    )
    # Thread the prefix-evidence and continuation-gap data so the missing-prefix
    # heuristic fires here the same way it does in live runtime. Previously this
    # test only passed `raw_lines`, which silently disabled the heuristic.
    actual = collect_screenshot_messages(
        debug_data["raw_lines"],
        line_ys_by_channel=debug_data.get("raw_line_ys"),
        raw_line_prefix_evidence_by_channel=debug_data.get("raw_line_prefix_evidence"),
        raw_continuation_y_gaps=debug_data.get("raw_continuation_y_gaps"),
    )

    _assert_channel_lines_match(
        fixture_name=png_path.name,
        channel_name="team_lines",
        actual_lines=actual["team_lines"],
        expected_lines=list(want_team),
    )
    _assert_channel_lines_match(
        fixture_name=png_path.name,
        channel_name="all_lines",
        actual_lines=actual["all_lines"],
        expected_lines=list(want_all),
    )
