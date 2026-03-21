"""Configuration defaults and user override loading.

This module provides:
- CONFIG: merged default + user config file values
- LOG_DIR: base folder for logs & snapshots
- CHAT_LOG / HERO_LOG / SNAP_DIR: derived paths

User config file (JSON) is loaded from one of these (in order):
1) OW_CHAT_LOGGER_CONFIG environment variable
2) %APPDATA%\\ow-chat-logger\\config.json (Windows)
3) ~/.ow-chat-logger/config.json (Unix fallback)

User config can override any CONFIG key, including "log_dir".
"""

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, Union

# ---------- defaults ----------
_DEFAULT_CONFIG: Dict[str, Any] = {
    "languages": ['en', 'de'],
    "screen_region": (50, 400, 500, 600),
    "scale_factor": 3,
    "y_merge_threshold": 18,
    "confidence_threshold": 0.7,
    "text_threshold": 0.5,

    # HSV bounds for chat text highlights (OpenCV HSV)
    # "team" (blue) and "all" (orange) chat colors in Overwatch
    "team_hsv_lower": [88, 135, 135],
    "team_hsv_upper": [112, 255, 255],
    "all_hsv_lower": [6, 155, 155],
    "all_hsv_upper": [20, 255, 255],

    # Default workspace for logs and snapshots.
    # This is overridden by a user config file or by the
    # OW_CHAT_LOG_DIR environment variable.
    "log_dir": str(Path(os.getenv("APPDATA", Path.home() / ".ow-chat-logger")) / "ow-chat-logger"),
    "capture_interval": 2.0,
    "max_remembered": 2000,
    # If True, try CUDA first; on failure EasyOCR falls back to CPU.
    "use_gpu": True,
}

IGNORED_SENDERS = {"team", "match"}
DEBUG_LEVEL = 2


def _get_user_config_path() -> Path:
    # Explicit override
    env_path = os.getenv("OW_CHAT_LOGGER_CONFIG")
    if env_path:
        return Path(env_path)

    # Windows common config location
    appdata = os.getenv("APPDATA")
    if appdata:
        return Path(appdata) / "ow-chat-logger" / "config.json"

    # Fallback (Unix-style)
    return Path.home() / ".ow-chat-logger" / "config.json"


def resolve_log_dir(path: Union[str, Path]) -> Path:
    """Expand %VAR% (e.g. %APPDATA%) and user home (~) in a log_dir string."""
    return Path(os.path.expandvars(str(path))).expanduser()


def _load_user_config() -> Dict[str, Any]:
    cfg_path = _get_user_config_path()
    if not cfg_path.exists():
        return {}

    try:
        return json.loads(cfg_path.read_text(encoding="utf-8"))
    except Exception as exc:
        print(
            f"Warning: could not load user config from {cfg_path}: {exc}",
            file=sys.stderr,
        )
        return {}


# Merge defaults + user config (user wins)
CONFIG: Dict[str, Any] = {**_DEFAULT_CONFIG, **_load_user_config()}

# Allow direct env var override for log dir
if (env_dir := os.getenv("OW_CHAT_LOG_DIR")):
    CONFIG["log_dir"] = env_dir

# Expand %APPDATA% and similar in JSON-provided paths (Windows / cross-platform)
if isinstance(CONFIG.get("log_dir"), str):
    CONFIG["log_dir"] = os.path.expandvars(CONFIG["log_dir"])

# Ensure folders exist
LOG_DIR = resolve_log_dir(CONFIG["log_dir"])
LOG_DIR.mkdir(parents=True, exist_ok=True)

CHAT_LOG = str(LOG_DIR / "chat_log.csv")
HERO_LOG = str(LOG_DIR / "hero_log.csv")

# Crash / debug logging
CRASH_LOG = str(LOG_DIR / "crash.log")

SNAP_DIR = str(LOG_DIR / "debug_snaps")
Path(SNAP_DIR).mkdir(parents=True, exist_ok=True)
