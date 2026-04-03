"""Unit tests for line classification and normalization."""

import pytest

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
    "line,expected_player,expected_msg",
    [
        ("[Foo : bar baz", "Foo", "bar baz"),
        ("Foo] : bar baz", "Foo", "bar baz"),
        ("[Foo bar baz", "Foo", "bar baz"),
        ("Foo] bar baz", "Foo", "bar baz"),
    ],
)
def test_classify_standard_when_one_bracket_is_missing(line, expected_player, expected_msg):
    r = classify_line(line)
    assert r["category"] == "standard"
    assert r["player"] == expected_player
    assert r["msg"] == expected_msg


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


@pytest.mark.parametrize(
    "line",
    [
        "A7X (Mercy) to Tloowy (Venture): Hello!",
        "A7X (Mercy) to Tloowy (Venture) Hello!",
    ],
)
def test_classify_targeted_hero_chat_as_system(line):
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


@pytest.mark.parametrize(
    "line",
    [
        "lol (you wish)",                      # parenthetical in plain text — no colon after )
        "someone joined (the server)",          # partial system-like text — no colon after )
    ],
)
def test_hero_pattern_not_triggered_without_colon(line):
    """HERO_PATTERN must not match lines where no colon follows the closing paren."""
    r = classify_line(line)
    assert r["category"] != "hero"


def test_hero_pattern_not_triggered_for_bracket_prefixed_line():
    """A standard-format line that contains parentheses must not be promoted to hero."""
    r = classify_line("[A7X]: great game (nice plays)")
    assert r["category"] == "standard"
    assert r["player"] == "A7X"
    assert "great game" in r["msg"]


def test_classify_continuation():
    r = classify_line("this is wrapped text")
    assert r["category"] == "continuation"


def test_classify_empty():
    assert classify_line("   ")["category"] == "empty"


def test_normalize_whitespace_and_semicolon():
    assert normalize("  a  b  ") == "a b"
    assert normalize("foo; bar") == "foo: bar"


def test_normalize_standard_prefix_spacing():
    assert normalize("[Foo] : bar baz") == "[Foo]: bar baz"
    assert normalize("[Foo]:bar baz") == "[Foo]: bar baz"


def test_normalize_pipe_to_I():
    assert normalize("| am here") == "I am here"


def test_contains_fragment_detects_system_message_fragment():
    assert contains_fragment("remember to act responsibly and report anything offensive")


def test_player_message_containing_channels_is_not_system():
    """Regression T-03: bare 'channels' pattern must not drop player chat containing that word."""
    r = classify_line("[A7X]: we should use different channels")
    assert r["category"] == "standard"
    assert r["player"] == "A7X"
    assert "channels" in r["msg"]
