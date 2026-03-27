"""Configuration defaults and lazy user override loading."""

from __future__ import annotations

import json
import os
import sys
from collections.abc import Iterator, MutableMapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_DEFAULT_CONFIG: dict[str, Any] = {
    "languages": ["en", "de"],
    "screen_region": (50, 400, 500, 600),
    "scale_factor": 3,
    "y_merge_threshold": 18,
    "confidence_threshold": 0.7,
    "text_threshold": 0.5,
    "team_hsv_lower": [88, 135, 135],
    "team_hsv_upper": [112, 255, 255],
    "all_hsv_lower": [6, 155, 155],
    "all_hsv_upper": [20, 255, 255],
    "log_dir": str(Path(os.getenv("APPDATA", Path.home() / ".ow-chat-logger")) / "ow-chat-logger"),
    "capture_interval": 2.0,
    "metrics_enabled": False,
    "metrics_interval_seconds": 10.0,
    "metrics_log_path": "performance_metrics.csv",
    "min_mask_nonzero_pixels_for_ocr": 24,
    "max_remembered": 2000,
    "use_gpu": True,
}

IGNORED_SENDERS = {"team", "match"}
DEBUG_LEVEL = 2

_cached_config: dict[str, Any] | None = None
_cached_paths: "AppPaths | None" = None


@dataclass(frozen=True)
class AppPaths:
    log_dir: Path
    chat_log: Path
    hero_log: Path
    crash_log: Path
    snap_dir: Path


class LazyConfig(MutableMapping[str, Any]):
    def _data(self) -> dict[str, Any]:
        return load_config()

    def __getitem__(self, key: str) -> Any:
        return self._data()[key]

    def __setitem__(self, key: str, value: Any) -> None:
        self._data()[key] = value
        reset_paths()

    def __delitem__(self, key: str) -> None:
        del self._data()[key]
        reset_paths()

    def __iter__(self) -> Iterator[str]:
        return iter(self._data())

    def __len__(self) -> int:
        return len(self._data())

    def __repr__(self) -> str:
        return repr(self._data())


def _get_user_config_path() -> Path:
    env_path = os.getenv("OW_CHAT_LOGGER_CONFIG")
    if env_path:
        return Path(env_path)

    appdata = os.getenv("APPDATA")
    if appdata:
        return Path(appdata) / "ow-chat-logger" / "config.json"

    return Path.home() / ".ow-chat-logger" / "config.json"


def resolve_log_dir(path: str | Path) -> Path:
    """Expand %VAR% (e.g. %APPDATA%) and user home (~) in a log_dir string."""
    return Path(os.path.expandvars(str(path))).expanduser()


def _load_user_config() -> dict[str, Any]:
    cfg_path = _get_user_config_path()
    if not cfg_path.exists():
        return {}

    try:
        data = json.loads(cfg_path.read_text(encoding="utf-8"))
    except Exception as exc:
        print(
            f"Warning: could not load user config from {cfg_path}: {exc}",
            file=sys.stderr,
        )
        return {}

    if not isinstance(data, dict):
        print(
            f"Warning: expected JSON object in user config {cfg_path}",
            file=sys.stderr,
        )
        return {}
    return data


def load_config(*, reload: bool = False) -> dict[str, Any]:
    global _cached_config
    if _cached_config is not None and not reload:
        return _cached_config

    config = {**_DEFAULT_CONFIG, **_load_user_config()}

    if env_dir := os.getenv("OW_CHAT_LOG_DIR"):
        config["log_dir"] = env_dir

    if isinstance(config.get("log_dir"), str):
        config["log_dir"] = os.path.expandvars(config["log_dir"])

    _cached_config = config
    return _cached_config


def reset_config() -> None:
    global _cached_config
    _cached_config = None
    reset_paths()


def get_app_paths(*, ensure_exists: bool = True) -> AppPaths:
    global _cached_paths
    if _cached_paths is not None:
        return _cached_paths

    config = load_config()
    log_dir = resolve_log_dir(config["log_dir"])
    paths = AppPaths(
        log_dir=log_dir,
        chat_log=log_dir / "chat_log.csv",
        hero_log=log_dir / "hero_log.csv",
        crash_log=log_dir / "crash.log",
        snap_dir=log_dir / "debug_snaps",
    )
    if ensure_exists:
        paths.log_dir.mkdir(parents=True, exist_ok=True)
        paths.snap_dir.mkdir(parents=True, exist_ok=True)
    _cached_paths = paths
    return _cached_paths


def reset_paths() -> None:
    global _cached_paths
    _cached_paths = None


CONFIG = LazyConfig()
