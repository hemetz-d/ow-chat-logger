"""T-44: crash-log fallback for the packaged exe entrypoint."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest


@pytest.fixture
def nuitka_entry_module():
    """Load packaging/nuitka_entry.py as a module without executing __main__."""
    entry_path = Path(__file__).resolve().parent.parent / "packaging" / "nuitka_entry.py"
    spec = importlib.util.spec_from_file_location("nuitka_entry_under_test", entry_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["nuitka_entry_under_test"] = module
    try:
        spec.loader.exec_module(module)
        yield module
    finally:
        sys.modules.pop("nuitka_entry_under_test", None)


def test_write_packaged_crash_log_writes_traceback_under_appdata(
    nuitka_entry_module, tmp_path, monkeypatch
):
    monkeypatch.setenv("APPDATA", str(tmp_path))

    try:
        raise RuntimeError("boom from T-44 test")
    except RuntimeError as exc:
        nuitka_entry_module._write_packaged_crash_log(exc)

    crash_log = tmp_path / "ow-chat-logger" / "crash.log"
    assert crash_log.exists()
    contents = crash_log.read_text(encoding="utf-8")
    assert "--- Crash on " in contents
    assert "RuntimeError: boom from T-44 test" in contents


def test_write_packaged_crash_log_appends_without_truncating(
    nuitka_entry_module, tmp_path, monkeypatch
):
    monkeypatch.setenv("APPDATA", str(tmp_path))

    for i in range(2):
        try:
            raise ValueError(f"crash-{i}")
        except ValueError as exc:
            nuitka_entry_module._write_packaged_crash_log(exc)

    contents = (tmp_path / "ow-chat-logger" / "crash.log").read_text(encoding="utf-8")
    assert "crash-0" in contents
    assert "crash-1" in contents
    assert contents.count("--- Crash on ") == 2


def test_write_packaged_crash_log_falls_back_when_appdata_unset(
    nuitka_entry_module, tmp_path, monkeypatch
):
    # Simulate a degraded environment where %APPDATA% isn't set. The helper
    # should fall back to the home directory rather than crashing itself —
    # a logging fallback that throws is strictly worse than silent.
    monkeypatch.delenv("APPDATA", raising=False)
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))

    try:
        raise RuntimeError("no-appdata")
    except RuntimeError as exc:
        nuitka_entry_module._write_packaged_crash_log(exc)

    fallback_log = tmp_path / ".ow-chat-logger" / "crash.log"
    assert fallback_log.exists()
    assert "no-appdata" in fallback_log.read_text(encoding="utf-8")


def test_write_packaged_crash_log_never_raises(nuitka_entry_module, monkeypatch):
    # If the filesystem write itself fails, the helper must swallow — the
    # caller is already handling an exception and re-raising; a secondary
    # failure from the logger would mask the original traceback.
    monkeypatch.setenv("APPDATA", "/this/path/should/not/be/writable/by/a/test")
    monkeypatch.setattr(
        Path,
        "mkdir",
        lambda *a, **kw: (_ for _ in ()).throw(OSError("denied")),
    )

    try:
        raise RuntimeError("ignored")
    except RuntimeError as exc:
        nuitka_entry_module._write_packaged_crash_log(exc)  # must not raise
