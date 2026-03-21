"""Pytest configuration: test log dir, OCR opt-in, shared fixtures."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

# Isolate log dir from real user config before ow_chat_logger.config is imported.
_TEST_LOG = Path(__file__).resolve().parent / "_test_log_dir"
_TEST_LOG.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("OW_CHAT_LOG_DIR", str(_TEST_LOG))


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--run-ocr",
        action="store_true",
        default=False,
        help="Run EasyOCR screenshot regression tests (slow; needs GPU/CPU time)",
    )


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    if config.getoption("--run-ocr"):
        return
    skip = pytest.mark.skip(
        reason="OCR regression tests skipped; run with: pytest --run-ocr",
    )
    for item in items:
        if "ocr" in item.keywords:
            item.add_marker(skip)


@pytest.fixture(scope="session")
def ocr_engine_session():
    """Heavy: loads EasyOCR once per session. Only used by @pytest.mark.ocr tests."""
    from ow_chat_logger.config import CONFIG
    from ow_chat_logger.ocr_engine import OCREngine

    return OCREngine(
        CONFIG["languages"],
        CONFIG["confidence_threshold"],
        CONFIG["text_threshold"],
        use_gpu=False,
    )
