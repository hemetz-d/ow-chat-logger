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
from ow_chat_logger.pipeline import extract_chat_lines

pytestmark = pytest.mark.ocr

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "regression"


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
    for png in sorted(FIXTURE_DIR.glob("*.png")):
        expected = FIXTURE_DIR / f"{png.stem}.expected.json"
        if expected.is_file():
            out.append((png, expected))
    return out


CASES = _discover_cases()


@pytest.mark.parametrize(
    "png_path,expected_path",
    CASES if CASES else [(None, None)],
    ids=[case[0].stem for case in CASES] if CASES else ["no-fixtures"],
)
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
    actual_lines = extract_chat_lines(
        rgb,
        ocr_engine_session,
        config_overrides=overrides,
        ocr_profile=ocr_profile_session,
    )
    actual = collect_screenshot_messages(actual_lines)

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
