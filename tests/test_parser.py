"""Unit tests for line classification and normalization."""

import pytest

from ow_chat_logger.ocr_engine import OCR_ALLOWLIST
from ow_chat_logger.parser import classify_line, contains_fragment, normalize


@pytest.mark.parametrize(
    "line,expected_cat",
    [
        ("[PlayerName] : hello", "standard"),
        ("[Player Name] : hi there", "standard"),
    ],
)
def test_classify_standard(line, expected_cat):
    r = classify_line(line)
    assert r["category"] == expected_cat
    assert r["player"].strip()
    assert "msg" in r


def test_classify_standard_strips_player():
    r = classify_line("[Foo] : bar baz")
    assert r["category"] == "standard"
    assert r["player"] == "Foo"
    assert r["msg"] == "bar baz"


@pytest.mark.parametrize(
    "line",
    [
        "Someone left the game",
        "Player has joined the voice channel",
        "Joined team voice chat - Push to talk",
    ],
)
def test_classify_system_regex(line):
    r = classify_line(line)
    assert r["category"] == "system"


def test_voice_lines_muted_is_system_not_concat_bug():
    """Regression: 'muted for' and 'team voice' must be separate patterns."""
    r = classify_line("Unlockable voice lines muted for this match")
    assert r["category"] == "system"


def test_classify_hero():
    r = classify_line("Alice (Tracer): hello")
    assert r["category"] == "hero"
    assert r["player"] == "Alice"
    assert r["hero"] == "Tracer"
    assert r["msg"] == "hello"


def test_classify_continuation():
    r = classify_line("this is wrapped text")
    assert r["category"] == "continuation"


def test_classify_empty():
    assert classify_line("   ")["category"] == "empty"


def test_normalize_whitespace_and_semicolon():
    assert normalize("  a  b  ") == "a b"
    assert normalize("foo; bar") == "foo: bar"


def test_normalize_pipe_to_I():
    assert normalize("| am here") == "I am here"


def test_contains_fragment_detects_system_message_fragment():
    assert contains_fragment("remember to act responsibly and report anything offensive")


def test_ocr_allowlist_contains_german_characters():
    for char in "üäöÜÄÖ§":
        assert char in OCR_ALLOWLIST
