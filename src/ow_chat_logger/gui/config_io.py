from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


def load_ui_config() -> dict[str, Any]:
    from ow_chat_logger.config import _DEFAULT_CONFIG, load_config

    cfg = load_config()
    defaults = _DEFAULT_CONFIG
    return {
        "screen_region": list(cfg.get("screen_region", defaults["screen_region"])),
        "capture_interval": cfg.get("capture_interval", defaults["capture_interval"]),
        "live_message_confirmations_required": cfg.get(
            "live_message_confirmations_required",
            defaults["live_message_confirmations_required"],
        ),
        "max_remembered": cfg.get("max_remembered", defaults["max_remembered"]),
        "ocr_default_profile": cfg.get(
            "ocr_default_profile", defaults["ocr"]["default_profile"]
        ),
        "team_hsv_lower": list(cfg.get("team_hsv_lower", defaults["team_hsv_lower"])),
        "team_hsv_upper": list(cfg.get("team_hsv_upper", defaults["team_hsv_upper"])),
        "all_hsv_lower": list(cfg.get("all_hsv_lower", defaults["all_hsv_lower"])),
        "all_hsv_upper": list(cfg.get("all_hsv_upper", defaults["all_hsv_upper"])),
    }


def save_ui_config(data: dict[str, Any]) -> None:
    from ow_chat_logger.config import get_user_config_path

    config_path: Path = get_user_config_path()
    existing: dict[str, Any] = {}
    if config_path.exists():
        try:
            existing = json.loads(config_path.read_text(encoding="utf-8"))
        except Exception:
            pass
    if not isinstance(existing, dict):
        existing = {}

    top_level_keys = (
        "screen_region",
        "capture_interval",
        "live_message_confirmations_required",
        "max_remembered",
        "team_hsv_lower",
        "team_hsv_upper",
        "all_hsv_lower",
        "all_hsv_upper",
    )
    for key in top_level_keys:
        if key in data:
            existing[key] = data[key]

    if "ocr_default_profile" in data:
        ocr = existing.get("ocr")
        if not isinstance(ocr, dict):
            ocr = {}
        ocr["default_profile"] = data["ocr_default_profile"]
        existing["ocr"] = ocr

    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(json.dumps(existing, indent=2), encoding="utf-8")


def get_available_ocr_profiles() -> list[str]:
    from ow_chat_logger.config import load_config

    cfg = load_config()
    return list((cfg.get("ocr") or {}).get("profiles", {}).keys())


def open_config_folder() -> None:
    from ow_chat_logger.config import default_appdata_dir

    folder = default_appdata_dir()
    folder.mkdir(parents=True, exist_ok=True)
    os.startfile(str(folder))


def open_log_folder() -> None:
    from ow_chat_logger.config import get_app_paths

    folder = get_app_paths().log_dir
    folder.mkdir(parents=True, exist_ok=True)
    os.startfile(str(folder))
