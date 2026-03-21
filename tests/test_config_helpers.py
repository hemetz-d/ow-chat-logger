"""Tests for config helpers (no full module reload)."""

import sys
from pathlib import Path

import pytest

from ow_chat_logger.config import resolve_log_dir


def test_resolve_log_dir_expanduser(monkeypatch, tmp_path):
    home = tmp_path
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    p = resolve_log_dir("~/ow-chat-logger")
    assert p == home / "ow-chat-logger"


@pytest.mark.skipif(sys.platform != "win32", reason="%APPDATA% expansion is Windows-specific")
def test_resolve_log_dir_appdata(monkeypatch, tmp_path):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    p = resolve_log_dir("%APPDATA%\\ow-chat-logger")
    assert p == tmp_path / "ow-chat-logger"
