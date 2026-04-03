"""Tests for config helpers (no full module reload)."""

import sys
from pathlib import Path

import pytest

from ow_chat_logger.config import CONFIG, resolve_log_dir


def test_resolve_log_dir_expanduser(monkeypatch):
    home = Path(__file__).resolve().parent / "_tmp_home"
    home.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    p = resolve_log_dir("~/ow-chat-logger")
    assert p == home / "ow-chat-logger"


@pytest.mark.skipif(sys.platform != "win32", reason="%APPDATA% expansion is Windows-specific")
def test_resolve_log_dir_appdata(monkeypatch):
    appdata = Path(__file__).resolve().parent / "_tmp_appdata"
    appdata.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("APPDATA", str(appdata))
    p = resolve_log_dir("%APPDATA%\\ow-chat-logger")
    assert p == appdata / "ow-chat-logger"


def test_lazy_config_is_read_only():
    with pytest.raises(TypeError):
        CONFIG["capture_interval"] = 99.0
