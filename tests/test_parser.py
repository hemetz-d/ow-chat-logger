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


@pytest.mark.parametrize(
    "line",
    [
        "You endorsed FlameHawk!",
        "You endorsed MimiChan!",
        "Music selected is Kicks (was Any)",
    ],
)
def test_classify_anchored_system_lines(line):
    """T-50 / priority #2: lines starting with `You endorsed ` or `Music selected
    is ` must be classified as system, not appended as continuation."""
    r = classify_line(line)
    assert r["category"] == "system"


@pytest.mark.parametrize(
    "line",
    [
        # Legitimate chat messages that happen to contain the substring mid-line.
        # The `^` anchor on the system pattern must prevent these from filtering.
        "[Alice]: I think you endorsed the wrong play",
        "[Bob]: the Music selected is bad",
    ],
)
def test_anchored_system_patterns_do_not_match_inside_chat_messages(line):
    """T-50 / priority #2 negative: the `^You endorsed ` and `^Music selected is`
    patterns are anchored to the line start and must not strip a real chat
    message that incidentally contains the same substring."""
    r = classify_line(line)
    assert r["category"] == "standard"


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


def test_classify_hero_preserves_raw_hero_text_for_later_canonicalization():
    r = classify_line("Alice (D. Va): hello")
    assert r["category"] == "hero"
    assert r["hero"] == "D. Va"


@pytest.mark.parametrize(
    "line",
    [
        "lol (you wish)",  # parenthetical in plain text — no colon after )
        "someone joined (the server)",  # partial system-like text — no colon after )
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


def test_normalize_pipe_preserved_in_message():
    """T-18: normalize() must not substitute | in message body — pipe substitution is player-only."""
    assert normalize("[A7X]: l|l") == "[A7X]: l|l"


def test_pipe_substituted_in_player_name_not_message():
    """T-18: | in player token becomes I; | in message body is left untouched."""
    r = classify_line("[A7X]: l|l")
    assert r["category"] == "standard"
    assert r["player"] == "A7X"
    assert r["msg"] == "l|l"


def test_pipe_in_player_name_becomes_I():
    """T-18: | appearing inside the player name brackets is corrected to I."""
    r = classify_line("[|ANATOR]: hello")
    assert r["category"] == "standard"
    assert r["player"] == "IANATOR"
    assert r["msg"] == "hello"


def test_multi_error_spaced_name_l_suffix():
    """T-19: missing brackets + spaces in name + l: suffix → standard, not continuation."""
    r = classify_line("A 7 X l: boris more healing pls")
    assert r["category"] == "standard"
    assert r["player"] == "A7X"
    assert r["msg"] == "boris more healing pls"


def test_multi_error_spaced_name_I_suffix():
    """T-19: capital-I variant of the ] misread works the same way."""
    r = classify_line("ZANGETSU I: hello dogges")
    assert r["category"] == "standard"
    assert r["player"] == "ZANGETSU"
    assert r["msg"] == "hello dogges"


def test_multi_error_player_segment_too_long_falls_through():
    """T-19: player segment exceeding the length cap must not be promoted to standard."""
    r = classify_line("this is way too long to be a player name l: something")
    assert r["category"] == "continuation"


def test_multi_error_does_not_eat_hero_lines():
    """T-19: a hero-format line with (hero) must not be claimed by the spaced-name pattern."""
    r = classify_line("Alice (Tracer): hello")
    assert r["category"] == "hero"


def test_hero_ban_vote_warning_is_system():
    """T-27: hero-ban vote warning must be classified as system, not continuation."""
    r = classify_line("Warning! You're voting to ban your teammate's preferred hero.")
    assert r["category"] == "system"


def test_contains_fragment_detects_system_message_fragment():
    assert contains_fragment("remember to act responsibly and report anything offensive")


def test_player_message_containing_channels_is_not_system():
    """Regression T-03: bare 'channels' pattern must not drop player chat containing that word."""
    r = classify_line("[A7X]: we should use different channels")
    assert r["category"] == "standard"
    assert r["player"] == "A7X"
    assert "channels" in r["msg"]
