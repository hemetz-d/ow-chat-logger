"""Dump per-fixture diagnostics: raw OCR boxes, masks, reconstructed lines.

Usage:
    python tools/dump_fixture.py example_14 example_18
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import cv2
import numpy as np

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

from ow_chat_logger.config import resolve_ocr_profile  # noqa: E402
from ow_chat_logger.ocr import build_ocr_backend  # noqa: E402
from ow_chat_logger.pipeline import extract_chat_debug_data  # noqa: E402

FIXTURE_DIR = REPO_ROOT / "tests" / "fixtures" / "regression"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("names", nargs="+", help="Fixture stems to dump.")
    args = parser.parse_args()

    profile = resolve_ocr_profile()
    ocr = build_ocr_backend(profile)

    for name in args.names:
        png = FIXTURE_DIR / f"{name}.png"
        if not png.is_file():
            print(f"missing: {png}")
            continue
        bgr = cv2.imread(str(png))
        rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
        debug = extract_chat_debug_data(rgb, ocr, ocr_profile=profile)

        for ch in ("team", "all"):
            mask = debug["masks"][ch]
            nz = int(np.count_nonzero(mask)) if mask is not None else 0
            print(f"=== {name} [{ch}] mask_nonzero={nz} ===")
            print(f"  raw_lines ({len(debug['raw_lines'][ch])}):")
            for line in debug["raw_lines"][ch]:
                print(f"    {line!r}")
            results = (debug.get("ocr_results") or {}).get(ch) or []
            print(f"  ocr_boxes ({len(results)}):")
            for bbox, text, conf in results:
                xs = [p[0] for p in bbox]
                ys = [p[1] for p in bbox]
                conf_str = "?" if conf is None else f"{conf:.2f}"
                print(
                    f"    x={min(xs):>4.0f}..{max(xs):>4.0f} y={min(ys):>4.0f}..{max(ys):>4.0f} "
                    f"conf={conf_str} {text!r}"
                )
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
