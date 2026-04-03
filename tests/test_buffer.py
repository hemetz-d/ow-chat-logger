"""Tests for MessageBuffer state machine."""

from ow_chat_logger.buffer import MessageBuffer


def test_feed_first_message_returns_none():
    b = MessageBuffer()
    assert b.feed("[p] : hi") is None
    assert b.current is not None
    assert b.current["category"] == "standard"


def test_feed_second_message_returns_first():
    b = MessageBuffer()
    b.feed("[a] : first")
    finished = b.feed("[b] : second")
    assert finished["player"] == "a"
    assert "first" in finished["msg"]
    assert b.current["player"] == "b"


def test_feed_lenient_new_message_returns_previous():
    b = MessageBuffer()
    b.feed("[a] : first")
    finished = b.feed("[b second")
    assert finished["player"] == "a"
    assert "first" in finished["msg"]
    assert b.current["player"] == "b"
    assert b.current["msg"] == "second"


def test_feed_lenient_new_message_with_missing_opening_bracket_returns_previous():
    b = MessageBuffer()
    b.feed("[a] : first")
    finished = b.feed("b] second")
    assert finished["player"] == "a"
    assert "first" in finished["msg"]
    assert b.current["player"] == "b"
    assert b.current["msg"] == "second"


def test_continuation_appends():
    b = MessageBuffer()
    b.feed("[a] : start")
    assert b.feed("more text") is None
    assert b.current["msg"].endswith("more text")


def test_system_clears_and_returns_previous():
    b = MessageBuffer()
    b.feed("[a] : hi")
    finished = b.feed("Player left the game")
    assert finished["player"] == "a"
    assert b.current is None


def test_targeted_hero_chat_system_line_does_not_append_to_previous_message():
    b = MessageBuffer()
    b.feed("[GrayOtter] : lil bro mad")
    finished = b.feed("A7X (Mercy) to Tloowy (Venture): Hello!")
    assert finished["player"] == "GrayOtter"
    assert finished["msg"] == "lil bro mad"
    assert b.current is None


def test_continuation_after_system_ignored():
    b = MessageBuffer()
    b.feed("system line left the game")
    assert b.feed("orphan continuation") is None
    assert b.current is None


def test_flush_returns_and_clears():
    b = MessageBuffer()
    b.feed("[x] : msg")
    f = b.flush()
    assert f["player"] == "x"
    assert b.current is None
    assert b.flush() is None
