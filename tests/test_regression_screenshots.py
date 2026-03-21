"""
Screenshot OCR regression: compare pipeline output to committed expected JSON.

Run (slow, loads EasyOCR):
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

from ow_chat_logger.pipeline import extract_chat_lines

pytestmark = pytest.mark.ocr

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "regression"


def _load_rgb(path: Path) -> np.ndarray:
    bgr = cv2.imread(str(path))
    assert bgr is not None, f"could not read image: {path}"
    return cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)


def _norm_line(s: str) -> str:
    return re.sub(r"\s+", " ", s.strip())


def _norm_lines(lines: list[str]) -> list[str]:
    return [_norm_line(x) for x in lines]


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


@pytest.mark.parametrize("png_path,expected_path", CASES if CASES else [(None, None)])
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

    # Lazy-load EasyOCR only when a real fixture exists (skip above avoids heavy import).
    ocr_engine_session = request.getfixturevalue("ocr_engine_session")

    raw = expected_path.read_text(encoding="utf-8")
    expected = json.loads(raw)

    overrides = expected.get("config_overrides") or {}
    want_team = expected.get("team_lines")
    want_all = expected.get("all_lines")
    assert want_team is not None, f"{expected_path}: missing team_lines"
    assert want_all is not None, f"{expected_path}: missing all_lines"

    rgb = _load_rgb(png_path)
    actual = extract_chat_lines(rgb, ocr_engine_session, config_overrides=overrides)

    assert _norm_lines(actual["team"]) == _norm_lines(list(want_team)), (
        f"team_lines mismatch for {png_path.name} — update {expected_path.name} if intentional."
    )
    assert _norm_lines(actual["all"]) == _norm_lines(list(want_all)), (
        f"all_lines mismatch for {png_path.name} — update {expected_path.name} if intentional."
    )
