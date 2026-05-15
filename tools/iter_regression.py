"""Quick iteration harness for regression fixtures.

Runs all fixtures through the same pipeline as the regression test, then prints
a per-fixture summary: PASS / FAIL with missing/unexpected lines.

Usage:
    python tools/iter_regression.py
    python tools/iter_regression.py --only example_18 example_25
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import cv2
import numpy as np

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

from ow_chat_logger.config import resolve_ocr_profile  # noqa: E402
from ow_chat_logger.message_processing import collect_screenshot_messages  # noqa: E402
from ow_chat_logger.ocr import build_ocr_backend  # noqa: E402
from ow_chat_logger.pipeline import extract_chat_debug_data  # noqa: E402

FIXTURE_DIR = REPO_ROOT / "tests" / "fixtures" / "regression"


def _natural_sort_key(path: Path) -> list[int | str]:
    parts = re.split(r"(\d+)", path.stem)
    return [int(part) if part.isdigit() else part.lower() for part in parts]


def _load_rgb(path: Path) -> np.ndarray:
    bgr = cv2.imread(str(path))
    if bgr is None:
        raise FileNotFoundError(f"could not read image: {path}")
    return cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s.strip())


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--only", nargs="*", default=None,
                        help="Only run the listed fixture stems (e.g. example_18).")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    profile = resolve_ocr_profile()
    ocr = build_ocr_backend(profile)

    pngs = sorted(FIXTURE_DIR.glob("*.png"), key=_natural_sort_key)
    results: list[tuple[str, bool, list[str], list[str], list[str], list[str]]] = []

    for png in pngs:
        expected_path = FIXTURE_DIR / f"{png.stem}.expected.json"
        if not expected_path.is_file():
            continue
        if args.only and png.stem not in args.only:
            continue

        expected = json.loads(expected_path.read_text(encoding="utf-8"))
        overrides = expected.get("config_overrides") or {}
        want_team = [_norm(x) for x in expected.get("team_lines") or []]
        want_all = [_norm(x) for x in expected.get("all_lines") or []]

        rgb = _load_rgb(png)
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
        got_team = [_norm(x) for x in actual["team_lines"]]
        got_all = [_norm(x) for x in actual["all_lines"]]

        pass_team = got_team == want_team
        pass_all = got_all == want_all
        passed = pass_team and pass_all
        results.append((png.stem, passed, want_team, got_team, want_all, got_all))

        status = "PASS" if passed else "FAIL"
        print(f"{status}  {png.stem}")
        if not passed or args.verbose:
            for ch_name, want, got in [
                ("team", want_team, got_team), ("all", want_all, got_all)
            ]:
                if want != got:
                    miss = [x for x in want if x not in got]
                    extra = [x for x in got if x not in want]
                    if miss:
                        print(f"    [{ch_name}] missing:")
                        for x in miss:
                            print(f"      - {x}")
                    if extra:
                        print(f"    [{ch_name}] unexpected:")
                        for x in extra:
                            print(f"      + {x}")

    total = len(results)
    passed = sum(1 for _, ok, *_ in results if ok)
    print(f"\nSummary: {passed}/{total} pass")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
