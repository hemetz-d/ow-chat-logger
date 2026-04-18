"""Nuitka packaging entrypoint for OW Chat Logger — defaults to GUI mode."""

import os
import sys
import time
import traceback
from pathlib import Path


def _write_packaged_crash_log(exc: BaseException) -> None:
    """Best-effort crash log for pre-GUI failures in the packaged exe.

    Uses stdlib only so a crash during ``ow_chat_logger`` import still lands.
    With the console hidden via ``--windows-console-mode=attach``, a traceback
    written to stderr vanishes when the user double-clicks from Explorer; this
    ensures there is always a file to read.
    """
    appdata = os.getenv("APPDATA")
    base = Path(appdata) / "ow-chat-logger" if appdata else Path.home() / ".ow-chat-logger"
    try:
        base.mkdir(parents=True, exist_ok=True)
        with (base / "crash.log").open("a", encoding="utf-8") as f:
            f.write(f"--- Crash on {time.strftime('%Y-%m-%dT%H:%M:%S')} ---\n")
            f.write("".join(traceback.format_exception(type(exc), exc, exc.__traceback__)))
            f.write("\n")
    except Exception:
        pass


if __name__ == "__main__":
    argv = sys.argv[1:]
    has_flag = any(
        a in ("--gui", "analyze", "benchmark", "--metrics", "--no-metrics", "--ocr-profile")
        for a in argv
    )
    if not has_flag:
        argv = ["--gui"] + argv
    try:
        from ow_chat_logger.main import main

        rc = main(argv)
    except Exception as exc:
        _write_packaged_crash_log(exc)
        raise
    sys.exit(rc)
