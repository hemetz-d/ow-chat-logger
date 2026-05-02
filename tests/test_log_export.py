"""Tests for the SQLite → CSV / TXT export layer.

Mirrors the seeding pattern from ``test_log_search.py`` — a tmp DB is
populated via direct ``INSERT`` so the test stays decoupled from the
``MessageLogger`` writer's contract.
"""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

from ow_chat_logger._chat_db import open_db
from ow_chat_logger.log_export import export_to_csv, export_to_txt


def _seed_db(
    db_path: Path,
    rows: list[tuple[str, str, str, str]],
) -> None:
    """Insert ``(timestamp, player, text, source)`` tuples into ``db_path``."""
    conn = open_db(db_path)
    try:
        for ts, player, text, source in rows:
            conn.execute(
                "INSERT INTO messages "
                "(timestamp, player, player_lc, text, text_lc, source) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (ts, player, player.lower(), text, text.lower(), source),
            )
        conn.commit()
    finally:
        conn.close()


@pytest.fixture
def seeded_db(tmp_path: Path) -> Path:
    db = tmp_path / "chat_log.sqlite"
    _seed_db(
        db,
        rows=[
            ("2026-01-01 09:00:00", "Alice", "Mercy", "hero"),
            ("2026-01-01 09:01:00", "Alice", "hi team", "team"),
            ("2026-01-01 09:02:00", "Bob", "GG WP", "all"),
            ("2026-01-01 09:03:00", "Bob", "Reinhardt", "hero"),
            ("2026-01-02 10:00:00", "Ünicode", "grüße dich", "all"),
            ("2026-01-02 10:01:00", "Eve", "go go go", "team"),
        ],
    )
    return db


# ── CSV ──────────────────────────────────────────────────────────────────────


def test_csv_writes_header_and_one_row_per_message(seeded_db: Path, tmp_path: Path):
    out = tmp_path / "history.csv"
    written = export_to_csv(out, db_path=seeded_db)
    assert written == 6

    with out.open(encoding="utf-8", newline="") as fh:
        rows = list(csv.reader(fh))

    assert rows[0] == ["timestamp", "player", "text", "source"]
    assert len(rows) == 7  # header + 6 data rows


def test_csv_chronological_order(seeded_db: Path, tmp_path: Path):
    out = tmp_path / "history.csv"
    export_to_csv(out, db_path=seeded_db)

    with out.open(encoding="utf-8", newline="") as fh:
        rows = list(csv.reader(fh))[1:]
    timestamps = [r[0] for r in rows]
    assert timestamps == sorted(timestamps)


def test_csv_channel_filter_restricts_source(seeded_db: Path, tmp_path: Path):
    out = tmp_path / "team.csv"
    written = export_to_csv(out, db_path=seeded_db, channel_filter="team")
    assert written == 2

    with out.open(encoding="utf-8", newline="") as fh:
        rows = list(csv.reader(fh))[1:]
    assert {r[3] for r in rows} == {"team"}


def test_csv_date_range_filter(seeded_db: Path, tmp_path: Path):
    out = tmp_path / "day1.csv"
    written = export_to_csv(
        out,
        db_path=seeded_db,
        since="2026-01-01 00:00:00",
        until="2026-01-01 23:59:59",
    )
    assert written == 4
    with out.open(encoding="utf-8", newline="") as fh:
        rows = list(csv.reader(fh))[1:]
    assert all(r[0].startswith("2026-01-01") for r in rows)


def test_csv_round_trip_matches_input(seeded_db: Path, tmp_path: Path):
    out = tmp_path / "history.csv"
    export_to_csv(out, db_path=seeded_db)

    with out.open(encoding="utf-8", newline="") as fh:
        rows = list(csv.reader(fh))[1:]

    expected = {
        ("2026-01-01 09:00:00", "Alice", "Mercy", "hero"),
        ("2026-01-01 09:01:00", "Alice", "hi team", "team"),
        ("2026-01-01 09:02:00", "Bob", "GG WP", "all"),
        ("2026-01-01 09:03:00", "Bob", "Reinhardt", "hero"),
        ("2026-01-02 10:00:00", "Ünicode", "grüße dich", "all"),
        ("2026-01-02 10:01:00", "Eve", "go go go", "team"),
    }
    assert {tuple(r) for r in rows} == expected


def test_csv_empty_db_writes_header_only(tmp_path: Path):
    db = tmp_path / "empty.sqlite"
    open_db(db).close()  # creates schema, no rows
    out = tmp_path / "out.csv"
    written = export_to_csv(out, db_path=db)
    assert written == 0
    with out.open(encoding="utf-8", newline="") as fh:
        rows = list(csv.reader(fh))
    assert rows == [["timestamp", "player", "text", "source"]]


def test_csv_missing_db_raises_clean_error(tmp_path: Path):
    db = tmp_path / "does-not-exist.sqlite"
    out = tmp_path / "out.csv"
    with pytest.raises(FileNotFoundError):
        export_to_csv(out, db_path=db)


# ── TXT ──────────────────────────────────────────────────────────────────────


def test_txt_row_shape_chat(seeded_db: Path, tmp_path: Path):
    out = tmp_path / "history.txt"
    written = export_to_txt(out, db_path=seeded_db, channel_filter="team")
    assert written == 2

    lines = out.read_text(encoding="utf-8").splitlines()
    assert lines[0] == "2026-01-01 09:01:00 | TEAM | Alice: hi team"
    assert lines[1] == "2026-01-02 10:01:00 | TEAM | Eve: go go go"


def test_txt_row_shape_hero_uses_slash(seeded_db: Path, tmp_path: Path):
    out = tmp_path / "history.txt"
    export_to_txt(out, db_path=seeded_db, channel_filter="hero")
    lines = out.read_text(encoding="utf-8").splitlines()
    # Hero rows: "<ts> | HERO | <player> / <hero>"
    assert lines[0] == "2026-01-01 09:00:00 | HERO | Alice / Mercy"
    assert lines[1] == "2026-01-01 09:03:00 | HERO | Bob / Reinhardt"


def test_txt_no_ansi_escapes(seeded_db: Path, tmp_path: Path):
    out = tmp_path / "history.txt"
    export_to_txt(out, db_path=seeded_db)
    body = out.read_text(encoding="utf-8")
    assert "\x1b[" not in body  # no ANSI CSI sequences


def test_txt_include_hero_false_excludes_hero_rows(seeded_db: Path, tmp_path: Path):
    out = tmp_path / "chat_only.txt"
    written = export_to_txt(out, db_path=seeded_db, include_hero=False)
    assert written == 4  # 2 team + 2 all

    body = out.read_text(encoding="utf-8")
    assert "HERO" not in body


def test_txt_channel_filter_excludes_correctly(seeded_db: Path, tmp_path: Path):
    out = tmp_path / "all_only.txt"
    written = export_to_txt(out, db_path=seeded_db, channel_filter="all")
    assert written == 2
    body = out.read_text(encoding="utf-8")
    assert "TEAM" not in body
    assert "HERO" not in body
    assert "ALL " in body  # 4-wide tag


def test_txt_empty_db_writes_empty_file(tmp_path: Path):
    db = tmp_path / "empty.sqlite"
    open_db(db).close()
    out = tmp_path / "out.txt"
    written = export_to_txt(out, db_path=db)
    assert written == 0
    assert out.read_text(encoding="utf-8") == ""


def test_txt_missing_db_raises_clean_error(tmp_path: Path):
    db = tmp_path / "missing.sqlite"
    out = tmp_path / "out.txt"
    with pytest.raises(FileNotFoundError):
        export_to_txt(out, db_path=db)


# ── Shared validation ───────────────────────────────────────────────────────


def test_invalid_channel_filter_raises(seeded_db: Path, tmp_path: Path):
    with pytest.raises(ValueError):
        export_to_csv(tmp_path / "x.csv", db_path=seeded_db, channel_filter="bogus")  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        export_to_txt(tmp_path / "x.txt", db_path=seeded_db, channel_filter="bogus")  # type: ignore[arg-type]


def test_export_does_not_mutate_db(seeded_db: Path, tmp_path: Path):
    """Read-only mode means the export never touches the canonical store."""
    before = seeded_db.stat().st_mtime_ns
    export_to_csv(tmp_path / "a.csv", db_path=seeded_db)
    export_to_txt(tmp_path / "a.txt", db_path=seeded_db)
    # Row count unchanged after both exports.
    conn = open_db(seeded_db)
    try:
        (count,) = conn.execute("SELECT COUNT(*) FROM messages").fetchone()
    finally:
        conn.close()
    assert count == 6
    # File mtime should be unchanged too (no writes via the export path).
    assert seeded_db.stat().st_mtime_ns == before
