"""On-demand debug snapshots for live-runtime parsing anomalies.

Opt-in via ``CONFIG["debug_snaps_on_anomaly"]``. Produces a cropped RGB
frame + channel masks + sidecar ``report.json`` whenever one of the
configured predicates fires. Saved under ``get_app_paths().snap_dir``
(``appdata_dir/dev/debug_snaps``), created lazily on first write.
"""

from __future__ import annotations

import datetime
import json
import re
import string
from pathlib import Path
from typing import Any, Mapping, Sequence

import cv2
import numpy as np

BASE_ALLOWED_CHARS: frozenset[str] = frozenset(
    string.ascii_letters + string.digits + " .,!?:;'\"()[]{}/\\-_@#$%&*+=<>|~^`"
)

LANGUAGE_EXTRA_CHARS: dict[str, str] = {
    "de": "äöüÄÖÜß",
}


def build_allowed_charset(languages: Sequence[str]) -> frozenset[str]:
    chars = set(BASE_ALLOWED_CHARS)
    for lang in languages:
        chars.update(LANGUAGE_EXTRA_CHARS.get(lang, ""))
    return frozenset(chars)


def has_bboxes_without_lines(debug_data: Mapping[str, Any]) -> bool:
    ocr_results = debug_data.get("ocr_results") or {}
    raw_lines = debug_data.get("raw_lines") or {}
    for channel in ("team", "all"):
        if len(ocr_results.get(channel) or []) > 0 and len(raw_lines.get(channel) or []) == 0:
            return True
    return False


def suspicious_chars_in(text: str, allowed_charset: frozenset[str]) -> list[str]:
    seen: list[str] = []
    for c in text:
        if c not in allowed_charset and c not in seen:
            seen.append(c)
    return seen


def contains_suspicious_characters(
    record: Mapping[str, Any],
    *,
    allowed_charset: frozenset[str],
    min_msg_length: int = 3,
) -> bool:
    if record.get("category") != "standard":
        return False
    msg = record.get("msg", "") or ""
    if len(msg) < min_msg_length:
        return False
    if not any(c.isalpha() for c in msg):
        return False
    return any(c not in allowed_charset for c in msg)


# Matches a bracketed `[name]` token embedded inside a message — i.e. preceded
# by non-whitespace and followed by more content. Fires on OCR-parser merges
# like `"J: hello [Makiko] hey"`, where two chat lines were welded into one
# record. Isolated trailing mentions (`"see [Makiko]"`) deliberately do not
# match: they lack the trailing content that indicates a second welded message.
_EMBEDDED_PREFIX_PATTERN = re.compile(r"\S\s*\[[^\[\]]{2,30}\]\s*:?\s*\S")


def message_contains_embedded_prefix(
    record: Mapping[str, Any],
    *,
    prefix_regex: re.Pattern[str] = _EMBEDDED_PREFIX_PATTERN,
) -> re.Match[str] | None:
    if record.get("category") != "standard":
        return None
    msg = record.get("msg", "") or ""
    return prefix_regex.search(msg)


def _timestamp_slug(now: datetime.datetime | None) -> str:
    now = now or datetime.datetime.now()
    return now.strftime("%Y%m%d-%H%M%S-%f")


def _write_png_rgb(path: Path, rgb: np.ndarray) -> None:
    cv2.imwrite(str(path), cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR))


def _write_png_mask(path: Path, mask: np.ndarray) -> None:
    cv2.imwrite(str(path), mask)


def save_anomaly_snapshot(
    debug_data: Mapping[str, Any],
    snap_dir: Path,
    *,
    reason: str,
    details: Mapping[str, Any] | None = None,
    now: datetime.datetime | None = None,
) -> Path:
    out_dir = snap_dir / _timestamp_slug(now)
    out_dir.mkdir(parents=True, exist_ok=True)

    rgb = debug_data.get("cropped_rgb_image")
    if rgb is not None:
        _write_png_rgb(out_dir / "cropped_rgb.png", np.asarray(rgb))

    masks = debug_data.get("masks") or {}
    for channel in ("team", "all"):
        mask = masks.get(channel)
        if mask is not None:
            _write_png_mask(out_dir / f"{channel}_mask.png", np.asarray(mask))

    report = {
        "reason": reason,
        "details": dict(details or {}),
        "raw_lines": debug_data.get("raw_lines"),
        "timings": debug_data.get("timings"),
        "ocr_box_counts": {
            ch: len((debug_data.get("ocr_results") or {}).get(ch) or []) for ch in ("team", "all")
        },
        "ocr_profile": (debug_data.get("config") or {}).get("ocr_profile"),
        "ocr_engine": (debug_data.get("config") or {}).get("ocr_engine"),
    }
    (out_dir / "report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )
    return out_dir
