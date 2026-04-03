"""Pytest configuration: test log dir, OCR opt-in, shared fixtures."""

from __future__ import annotations

import os
from pathlib import Path
from uuid import uuid4

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
        help="Run OCR screenshot regression tests",
    )
    parser.addoption(
        "--ocr-profile",
        action="store",
        default=None,
        help="OCR profile name for OCR-enabled regression tests.",
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
def ocr_profile_session(pytestconfig: pytest.Config):
    from ow_chat_logger.config import resolve_ocr_profile

    return resolve_ocr_profile(profile_name=pytestconfig.getoption("--ocr-profile"))


@pytest.fixture(scope="session")
def ocr_engine_session(ocr_profile_session):
    """Loads the selected OCR backend once per session for @pytest.mark.ocr tests."""
    from ow_chat_logger.ocr import OCRBackendUnavailableError, build_ocr_backend

    try:
        return build_ocr_backend(ocr_profile_session)
    except OCRBackendUnavailableError as exc:
        pytest.skip(str(exc))


@pytest.fixture
def local_tmp_dir():
    def factory(name: str) -> Path:
        path = _TEST_LOG / f"{name}-{uuid4().hex}"
        path.mkdir(parents=True, exist_ok=True)
        return path

    return factory
