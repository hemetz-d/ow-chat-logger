"""DuplicateFilter behavior."""

from ow_chat_logger.deduplication import DuplicateFilter


def test_zero_max_remembered_clamped_no_crash():
    f = DuplicateFilter(0)
    assert f.is_new("a")
    assert not f.is_new("a")
    assert f.is_new("b")


def test_remembers_within_window():
    f = DuplicateFilter(3)
    assert f.is_new("a")
    assert f.is_new("b")
    assert f.is_new("c")
    assert not f.is_new("a")  # still in window
    assert f.is_new(
        "d"
    )  # evicts oldest if full — actually capacity 3, after a,b,c queue full; d evicts a
    assert f.is_new("a")  # a was evicted, so "new" again


def test_duplicate_returns_false():
    f = DuplicateFilter(100)
    assert f.is_new("k")
    assert not f.is_new("k")
