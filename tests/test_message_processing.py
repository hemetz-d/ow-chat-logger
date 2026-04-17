from unittest.mock import MagicMock

from ow_chat_logger.buffer import MessageBuffer
from ow_chat_logger.hero_roster import canonicalize_hero_name
from ow_chat_logger.message_processing import (
    normalize_finished_message,
    collect_screenshot_messages,
    process_finished,
    process_lines,
)


def test_process_finished_standard_logs_once():
    chat_dedup = MagicMock()
    chat_dedup.is_new.return_value = True
    hero_dedup = MagicMock()
    chat_logger = MagicMock()
    hero_logger = MagicMock()

    finished = {
        "category": "standard",
        "player": "Alice",
        "hero": "",
        "msg": "hello",
    }

    process_finished(
        finished,
        "team",
        chat_dedup=chat_dedup,
        hero_dedup=hero_dedup,
        chat_logger=chat_logger,
        hero_logger=hero_logger,
    )

    chat_logger.log.assert_called_once()
    hero_logger.log.assert_not_called()
    assert chat_dedup.is_new.called


def test_process_finished_ignores_ignored_senders():
    chat_logger = MagicMock()
    process_finished(
        {
            "category": "standard",
            "player": "team",
            "hero": "",
            "msg": "spam",
        },
        "all",
        chat_dedup=MagicMock(),
        hero_dedup=MagicMock(),
        chat_logger=chat_logger,
        hero_logger=MagicMock(),
    )
    chat_logger.log.assert_not_called()


def test_process_finished_none_noop():
    chat_logger = MagicMock()
    process_finished(
        None,
        "team",
        chat_dedup=MagicMock(),
        hero_dedup=MagicMock(),
        chat_logger=chat_logger,
        hero_logger=MagicMock(),
    )
    chat_logger.log.assert_not_called()


def test_process_lines_does_not_carry_continuation_between_screenshots():
    chat_logger = MagicMock()
    team_buffer = MessageBuffer()
    all_buffer = MessageBuffer()
    chat_dedup = MagicMock()
    chat_dedup.is_new.return_value = True

    process_lines(
        {"team": ["[Alice] : hello"], "all": []},
        team_buffer,
        all_buffer,
        chat_dedup=chat_dedup,
        hero_dedup=MagicMock(),
        chat_logger=chat_logger,
        hero_logger=MagicMock(),
    )

    process_lines(
        {"team": ["continued text"], "all": []},
        team_buffer,
        all_buffer,
        chat_dedup=chat_dedup,
        hero_dedup=MagicMock(),
        chat_logger=chat_logger,
        hero_logger=MagicMock(),
    )

    assert chat_logger.log.call_count == 1


def test_collect_screenshot_messages_reuses_app_filtering_rules():
    actual = collect_screenshot_messages(
        {
            "team": [
                "Joined team voice chat - Push to talk",
                "MiniNinja (Bastion): We need a healer",
            ],
            "all": [
                "7",
                "[Smokeelite3] : that was embarrassing",
            ],
        }
    )

    assert actual == {
        "team_lines": [],
        "all_lines": ["[Smokeelite3]: that was embarrassing"],
    }


def test_collect_screenshot_messages_can_include_hero_lines():
    actual = collect_screenshot_messages(
        {
            "team": ["MiniNinja (Bastion): We need a healer"],
            "all": [],
        },
        include_hero_lines=True,
    )

    assert actual == {
        "team_lines": ["MiniNinja (Bastion): We need a healer"],
        "all_lines": [],
    }


def test_collect_screenshot_messages_strips_trailing_report_suffix():
    actual = collect_screenshot_messages(
        {
            "team": [],
            "all": ["[Smokeelite3] : offensive message [Report]"],
        }
    )

    assert actual == {
        "team_lines": [],
        "all_lines": ["[Smokeelite3]: offensive message"],
    }


def test_collect_screenshot_messages_fixes_trailing_l_in_player_prefix():
    actual = collect_screenshot_messages(
        {
            "team": ["[A7Xl: hello dogges"],
            "all": [],
        }
    )

    assert actual == {
        "team_lines": ["[A7X]: hello dogges"],
        "all_lines": [],
    }


def test_collect_screenshot_messages_fixes_trailing_capital_I_in_player_prefix():
    # OCR reads ']' as capital 'I': "[ZANGETSUI: hello" → "[ZANGETSU]: hello"
    actual = collect_screenshot_messages(
        {
            "team": ["[ZANGETSUI: hello"],
            "all": [],
        }
    )

    assert actual == {
        "team_lines": ["[ZANGETSU]: hello"],
        "all_lines": [],
    }


def test_continuation_discarded_when_y_gap_exceeds_threshold():
    buffer = MessageBuffer()
    buffer.feed("[Alice] : hello", y=10.0)
    buffer.feed("extra text", y=90.0, max_y_gap=50.0)  # gap = 80 > 50 → discarded
    result = buffer.flush()
    assert result["msg"] == "hello"


def test_continuation_appended_when_y_gap_within_threshold():
    buffer = MessageBuffer()
    buffer.feed("[Alice] : hello", y=10.0)
    buffer.feed("extra text", y=50.0, max_y_gap=50.0)  # gap = 40 ≤ 50 → appended
    result = buffer.flush()
    assert result["msg"] == "hello extra text"


def test_continuation_gap_ignored_when_threshold_is_none():
    buffer = MessageBuffer()
    buffer.feed("[Alice] : hello", y=10.0)
    buffer.feed("extra text", y=9999.0, max_y_gap=None)  # huge gap but no threshold
    result = buffer.flush()
    assert result["msg"] == "hello extra text"


def test_continuation_with_prefix_evidence_starts_unknown_message():
    actual = collect_screenshot_messages(
        {
            "team": ["[Alice] : hello", "YO"],
            "all": [],
        },
        raw_line_prefix_evidence_by_channel={
            "team": [
                {"has_missing_prefix_evidence": False},
                {"has_missing_prefix_evidence": True},
            ],
            "all": [],
        },
    )

    assert actual == {
        "team_lines": ["[Alice]: hello", "[unknown]: YO"],
        "all_lines": [],
    }


def test_continuation_without_prefix_evidence_stays_appended():
    actual = collect_screenshot_messages(
        {
            "team": ["[Alice] : hello", "extra text"],
            "all": [],
        },
        raw_line_prefix_evidence_by_channel={
            "team": [
                {"has_missing_prefix_evidence": False},
                {"has_missing_prefix_evidence": False},
            ],
            "all": [],
        },
    )

    assert actual == {
        "team_lines": ["[Alice]: hello extra text"],
        "all_lines": [],
    }


def test_prefix_evidence_can_start_unknown_without_existing_message():
    actual = collect_screenshot_messages(
        {
            "team": ["YO"],
            "all": [],
        },
        raw_line_prefix_evidence_by_channel={
            "team": [{"has_missing_prefix_evidence": True}],
            "all": [],
        },
    )

    assert actual == {
        "team_lines": ["[unknown]: YO"],
        "all_lines": [],
    }


def test_prefix_evidence_overrides_large_y_gap_and_starts_unknown():
    actual = collect_screenshot_messages(
        {
            "team": ["[Alice] : hello", "YO"],
            "all": [],
        },
        line_ys_by_channel={"team": [10.0, 200.0], "all": []},
        raw_line_prefix_evidence_by_channel={
            "team": [
                {"has_missing_prefix_evidence": False},
                {"has_missing_prefix_evidence": True},
            ],
            "all": [],
        },
        raw_continuation_y_gaps={"team": 50.0, "all": None},
    )

    assert actual == {
        "team_lines": ["[Alice]: hello", "[unknown]: YO"],
        "all_lines": [],
    }


def test_collect_screenshot_messages_strips_report_suffix_for_hero_lines_when_enabled():
    actual = collect_screenshot_messages(
        {
            "team": ["MiniNinja (Bastion): We need a healer [Report]"],
            "all": [],
        },
        include_hero_lines=True,
    )

    assert actual == {
        "team_lines": ["MiniNinja (Bastion): We need a healer"],
        "all_lines": [],
    }


def test_normalize_finished_message_canonicalizes_hero_variants():
    actual = normalize_finished_message(
        {
            "category": "hero",
            "player": "MiniNinja",
            "hero": "D. Va",
            "msg": "group up",
        },
        "team",
    )

    assert actual["hero"] == "D.Va"


def test_canonicalize_hero_name_accepts_sierra():
    assert canonicalize_hero_name("sierra") == "Sierra"


def test_normalize_finished_message_drops_unknown_hero():
    actual = normalize_finished_message(
        {
            "category": "hero",
            "player": "MiniNinja",
            "hero": "DefinitelyNotAHero",
            "msg": "group up",
        },
        "team",
    )

    assert actual is None


def test_process_finished_dedups_canonicalized_hero_variants():
    hero_dedup = MagicMock()
    hero_dedup.is_new.return_value = True
    hero_logger = MagicMock()

    process_finished(
        {
            "category": "hero",
            "player": "MiniNinja",
            "hero": "D Va",
            "msg": "group up",
        },
        "team",
        chat_dedup=MagicMock(),
        hero_dedup=hero_dedup,
        chat_logger=MagicMock(),
        hero_logger=hero_logger,
    )

    hero_dedup.is_new.assert_called_once_with("MiniNinja|D.Va")
    hero_logger.log.assert_called_once()


def test_collect_screenshot_messages_canonicalizes_hero_name_when_enabled():
    actual = collect_screenshot_messages(
        {
            "team": ["MiniNinja (Lucio): We need a healer"],
            "all": [],
        },
        include_hero_lines=True,
    )

    assert actual == {
        "team_lines": ["MiniNinja (Lúcio): We need a healer"],
        "all_lines": [],
    }
