from __future__ import annotations

import datetime
import json

import numpy as np
import pytest

from ow_chat_logger.debug_snaps import (
    build_allowed_charset,
    contains_suspicious_characters,
    has_bboxes_without_lines,
    message_contains_embedded_prefix,
    save_anomaly_snapshot,
    suspicious_chars_in,
)


def _base_debug_data(ocr_team=(), ocr_all=(), lines_team=(), lines_all=()) -> dict:
    return {
        "cropped_rgb_image": np.zeros((4, 4, 3), dtype=np.uint8),
        "masks": {
            "team": np.zeros((4, 4), dtype=np.uint8),
            "all": np.zeros((4, 4), dtype=np.uint8),
        },
        "ocr_results": {"team": list(ocr_team), "all": list(ocr_all)},
        "raw_lines": {"team": list(lines_team), "all": list(lines_all)},
        "timings": {"preprocess_seconds": 0.0, "ocr_seconds": 0.0, "parse_seconds": 0.0},
        "config": {"ocr_profile": "p", "ocr_engine": "e"},
    }


def test_has_bboxes_without_lines_fires_when_boxes_but_no_lines():
    data = _base_debug_data(ocr_team=["box"], lines_team=[])
    assert has_bboxes_without_lines(data) is True


def test_has_bboxes_without_lines_false_when_lines_present():
    data = _base_debug_data(ocr_team=["box"], lines_team=["hello"])
    assert has_bboxes_without_lines(data) is False


def test_has_bboxes_without_lines_false_when_no_boxes():
    assert has_bboxes_without_lines(_base_debug_data()) is False


def test_contains_suspicious_characters_true_for_bullet():
    charset = build_allowed_charset(["en"])
    record = {"category": "standard", "msg": "• hell amers aka dogs"}
    assert contains_suspicious_characters(record, allowed_charset=charset) is True


def test_contains_suspicious_characters_false_for_clean_chat():
    charset = build_allowed_charset(["en"])
    record = {"category": "standard", "msg": "hello friends gg"}
    assert contains_suspicious_characters(record, allowed_charset=charset) is False


def test_contains_suspicious_characters_allows_german_umlauts_when_de_enabled():
    charset = build_allowed_charset(["en", "de"])
    record = {"category": "standard", "msg": "hallo welt äöüß"}
    assert contains_suspicious_characters(record, allowed_charset=charset) is False


def test_contains_suspicious_characters_flags_umlauts_when_de_disabled():
    charset = build_allowed_charset(["en"])
    record = {"category": "standard", "msg": "hallo welt äöüß"}
    assert contains_suspicious_characters(record, allowed_charset=charset) is True


def test_contains_suspicious_characters_false_for_short_message():
    charset = build_allowed_charset(["en"])
    record = {"category": "standard", "msg": "•"}
    assert contains_suspicious_characters(record, allowed_charset=charset) is False


def test_contains_suspicious_characters_false_when_no_alpha():
    charset = build_allowed_charset(["en"])
    record = {"category": "standard", "msg": "111 !!!"}
    assert contains_suspicious_characters(record, allowed_charset=charset) is False


def test_contains_suspicious_characters_ignores_non_chat_records():
    charset = build_allowed_charset(["en"])
    record = {"category": "hero", "msg": "• Tracer"}
    assert contains_suspicious_characters(record, allowed_charset=charset) is False


def test_message_contains_embedded_prefix_fires_on_joebar_example():
    # Real production observation: `Joebar: J: hello [Makiko] hey` was logged
    # as a single record. The embedded `[Makiko]` flags the upstream merge.
    record = {"category": "standard", "player": "Joebar", "msg": "J: hello [Makiko] hey"}
    match = message_contains_embedded_prefix(record)
    assert match is not None
    assert "[Makiko]" in match.group(0)


def test_message_contains_embedded_prefix_fires_on_bracketed_colon_variant():
    record = {"category": "standard", "player": "Alice", "msg": "foo [Bob]: bar"}
    assert message_contains_embedded_prefix(record) is not None


def test_message_contains_embedded_prefix_ignores_at_mention():
    # `@Joebar` is not a chat prefix; must not fire.
    record = {"category": "standard", "player": "Alice", "msg": "tell @Joebar hi"}
    assert message_contains_embedded_prefix(record) is None


def test_message_contains_embedded_prefix_ignores_trailing_name_reference():
    # A bracket that ends the message isn't a welded second line.
    record = {"category": "standard", "player": "Alice", "msg": "see [Makiko]"}
    assert message_contains_embedded_prefix(record) is None


def test_message_contains_embedded_prefix_ignores_hero_category():
    record = {"category": "hero", "player": "Alice", "msg": "J: hello [Makiko] hey"}
    assert message_contains_embedded_prefix(record) is None


def test_suspicious_chars_in_returns_unique_offenders_in_order():
    charset = build_allowed_charset(["en"])
    assert suspicious_chars_in("a§b•c§d", charset) == ["§", "•"]


def test_save_anomaly_snapshot_writes_expected_files_and_report(tmp_path):
    snap_dir = tmp_path / "debug_snaps"
    assert not snap_dir.exists()

    data = _base_debug_data(ocr_team=["box"], lines_team=[])
    now = datetime.datetime(2026, 4, 17, 12, 34, 56, 789000)

    out_dir = save_anomaly_snapshot(
        data,
        snap_dir,
        reason="bboxes_without_lines",
        details={"ocr_box_counts": {"team": 1, "all": 0}},
        now=now,
    )

    assert out_dir.parent == snap_dir
    assert (out_dir / "cropped_rgb.png").exists()
    assert (out_dir / "team_mask.png").exists()
    assert (out_dir / "all_mask.png").exists()

    report = json.loads((out_dir / "report.json").read_text(encoding="utf-8"))
    assert report["reason"] == "bboxes_without_lines"
    assert report["details"] == {"ocr_box_counts": {"team": 1, "all": 0}}
    assert report["ocr_box_counts"] == {"team": 1, "all": 0}
    assert report["ocr_profile"] == "p"
