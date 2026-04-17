"""Nuitka packaging entrypoint for OW Chat Logger — defaults to GUI mode."""

import sys

from ow_chat_logger.main import main


if __name__ == "__main__":
    # Packaged exe defaults to GUI unless a subcommand or explicit flag is given
    argv = sys.argv[1:]
    has_flag = any(a in ("--gui", "analyze", "benchmark", "--metrics", "--ocr-profile") for a in argv)
    if not has_flag:
        argv = ["--gui"] + argv
    sys.exit(main(argv))
