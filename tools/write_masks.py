"""Write team/all masks (upscaled) to disk for a fixture for visual inspection."""

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
    parser.add_argument("names", nargs="+")
    parser.add_argument("--outdir", default=str(REPO_ROOT / "_mask_dump"))
    args = parser.parse_args()

    out_dir = Path(args.outdir)
    out_dir.mkdir(parents=True, exist_ok=True)

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
            print(f"{name}/{ch}: nonzero={nz} shape={mask.shape if mask is not None else None}")
            if mask is not None:
                cv2.imwrite(str(out_dir / f"{name}_{ch}.png"), mask)
        cropped = debug["cropped_rgb_image"]
        cv2.imwrite(str(out_dir / f"{name}_cropped.png"), cv2.cvtColor(cropped, cv2.COLOR_RGB2BGR))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
