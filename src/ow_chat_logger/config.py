"""Configuration defaults and lazy user override loading."""

from __future__ import annotations

import json
import os
import sys
from collections.abc import Iterator, Mapping
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ow_chat_logger.ocr import ResolvedOCRProfile

LEGACY_OCR_FLAT_KEYS = {
    "languages",
    "scale_factor",
    "high_quality_ocr",
    "y_merge_threshold",
    "max_continuation_y_gap_factor",
    "missing_prefix_min_anchor_lines",
    "missing_prefix_body_start_tolerance",
    "missing_prefix_span_right_padding",
    "missing_prefix_vertical_padding",
    "missing_prefix_min_span_nonzero_pixels",
    "missing_prefix_min_span_density",
    "missing_prefix_max_span_density",
    "missing_prefix_max_largest_component_fraction",
    "missing_prefix_min_line_height_fraction",
    "missing_prefix_max_line_height_fraction",
    "min_box_height_fraction",
    "min_component_area",
    "team_hsv_lower",
    "team_hsv_upper",
    "all_hsv_lower",
    "all_hsv_upper",
    "min_mask_nonzero_pixels_for_ocr",
    "confidence_threshold",
    "text_threshold",
    "use_gpu",
}

PIPELINE_CONFIG_KEYS = {
    "scale_factor",
    "high_quality_ocr",
    "y_merge_threshold",
    "max_continuation_y_gap_factor",
    "missing_prefix_min_anchor_lines",
    "missing_prefix_body_start_tolerance",
    "missing_prefix_span_right_padding",
    "missing_prefix_vertical_padding",
    "missing_prefix_min_span_nonzero_pixels",
    "missing_prefix_min_span_density",
    "missing_prefix_max_span_density",
    "missing_prefix_max_largest_component_fraction",
    "missing_prefix_min_line_height_fraction",
    "missing_prefix_max_line_height_fraction",
    "min_box_height_fraction",
    "min_component_area",
    "team_hsv_lower",
    "team_hsv_upper",
    "all_hsv_lower",
    "all_hsv_upper",
    "min_mask_nonzero_pixels_for_ocr",
}

ENGINE_SETTING_KEYS = {
    "confidence_threshold",
    "text_threshold",
    "use_gpu",
}

DEFAULT_OCR_PROFILE = "windows_default"
EASYOCR_MASTER_BASELINE_PROFILE = "easyocr_master_baseline"
TESSERACT_DEFAULT_PROFILE = "tesseract_default"
PACKAGED_OUTPUT_DIR_NAME = "OW Chat Logger Data"


def _builtin_ocr_profiles() -> dict[str, dict[str, Any]]:
    return {
        DEFAULT_OCR_PROFILE: {
            "engine": "windows",
            "languages": ["en", "de"],
            "pipeline": {
                "scale_factor": 4,
                "high_quality_ocr": True,
                "y_merge_threshold": 14,
                "max_continuation_y_gap_factor": 2.0,
                "missing_prefix_min_anchor_lines": 2,
                "missing_prefix_body_start_tolerance": 20.0,
                "missing_prefix_span_right_padding": 8,
                "missing_prefix_vertical_padding": 8,
                "missing_prefix_min_span_nonzero_pixels": 1000,
                "missing_prefix_min_span_density": 0.12,
                "missing_prefix_max_span_density": 0.5,
                "missing_prefix_max_largest_component_fraction": 0.8,
                "missing_prefix_min_line_height_fraction": 0.65,
                "missing_prefix_max_line_height_fraction": 1.6,
                "min_box_height_fraction": 0.55,
                "min_component_area": 0,
                "team_hsv_lower": [96, 190, 90],
                "team_hsv_upper": [118, 255, 255],
                "all_hsv_lower": [0, 150, 100],
                "all_hsv_upper": [20, 255, 255],
                "min_mask_nonzero_pixels_for_ocr": 24,
            },
            "settings": {},
        },
        EASYOCR_MASTER_BASELINE_PROFILE: {
            "engine": "easyocr",
            "languages": ["en", "de"],
            "pipeline": {
                "scale_factor": 3,
                "high_quality_ocr": False,
                "y_merge_threshold": 18,
                "max_continuation_y_gap_factor": 2.0,
                "missing_prefix_min_anchor_lines": 2,
                "missing_prefix_body_start_tolerance": 20.0,
                "missing_prefix_span_right_padding": 8,
                "missing_prefix_vertical_padding": 8,
                "missing_prefix_min_span_nonzero_pixels": 1000,
                "missing_prefix_min_span_density": 0.12,
                "missing_prefix_max_span_density": 0.5,
                "missing_prefix_max_largest_component_fraction": 0.8,
                "missing_prefix_min_line_height_fraction": 0.65,
                "missing_prefix_max_line_height_fraction": 1.6,
                "min_box_height_fraction": 0.55,
                "min_component_area": 0,
                "team_hsv_lower": [84, 90, 90],
                "team_hsv_upper": [112, 255, 255],
                "all_hsv_lower": [0, 100, 100],
                "all_hsv_upper": [20, 255, 255],
                "min_mask_nonzero_pixels_for_ocr": 24,
            },
            "settings": {
                "confidence_threshold": 0.7,
                "text_threshold": 0.5,
                "use_gpu": True,
            },
        },
        TESSERACT_DEFAULT_PROFILE: {
            "engine": "tesseract",
            "languages": ["eng", "deu"],
            "pipeline": {
                "scale_factor": 4,
                "high_quality_ocr": True,
                "y_merge_threshold": 16,
                "max_continuation_y_gap_factor": 2.0,
                "missing_prefix_min_anchor_lines": 2,
                "missing_prefix_body_start_tolerance": 20.0,
                "missing_prefix_span_right_padding": 8,
                "missing_prefix_vertical_padding": 8,
                "missing_prefix_min_span_nonzero_pixels": 1000,
                "missing_prefix_min_span_density": 0.12,
                "missing_prefix_max_span_density": 0.5,
                "missing_prefix_max_largest_component_fraction": 0.8,
                "missing_prefix_min_line_height_fraction": 0.65,
                "missing_prefix_max_line_height_fraction": 1.6,
                "min_box_height_fraction": 0.55,
                "min_component_area": 0,
                "team_hsv_lower": [96, 190, 90],
                "team_hsv_upper": [118, 255, 255],
                "all_hsv_lower": [0, 150, 100],
                "all_hsv_upper": [20, 255, 255],
                "min_mask_nonzero_pixels_for_ocr": 24,
            },
            "settings": {
                "language": "eng+deu",
                "psm": 6,
                "oem": 3,
                "allowlist": (
                    "abcdefghijklmnopqrstuvwxyz"
                    "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
                    "0123456789"
                    '# :[]*!?.,-üäöÜÄÖ+#()&%$§"='
                ),
                "confidence_threshold": 0.0,
                "executable_path": "",
                "extra_config": "",
            },
        },
    }


def _deep_merge_dict(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge_dict(merged[key], value)
        else:
            merged[key] = deepcopy(value)
    return merged

_DEFAULT_CONFIG: dict[str, Any] = {
    "languages": ["en", "de"],
    "screen_region": (80, 400, 400, 600),
    "scale_factor": 4,
    "high_quality_ocr": True,
    "y_merge_threshold": 14,
    "max_continuation_y_gap_factor": 2.0,
    "missing_prefix_min_anchor_lines": 2,
    "missing_prefix_body_start_tolerance": 20.0,
    "missing_prefix_span_right_padding": 8,
    "missing_prefix_vertical_padding": 8,
    "missing_prefix_min_span_nonzero_pixels": 1000,
    "missing_prefix_min_span_density": 0.12,
    "missing_prefix_max_span_density": 0.5,
    "missing_prefix_max_largest_component_fraction": 0.8,
    "missing_prefix_min_line_height_fraction": 0.65,
    "missing_prefix_max_line_height_fraction": 1.6,
    "min_component_area": 0,
    "team_hsv_lower": [96, 190, 90],
    "team_hsv_upper": [118, 255, 255],
    "all_hsv_lower": [0, 150, 100],
    "all_hsv_upper": [20, 255, 255],
    "capture_interval": 2.0,
    "metrics_enabled": False,
    "metrics_interval_seconds": 10.0,
    "metrics_log_path": None,
    "live_message_confirmations_required": 2,
    "min_mask_nonzero_pixels_for_ocr": 24,
    "max_remembered": 1000,
    "ocr": {
        "default_profile": DEFAULT_OCR_PROFILE,
        "profiles": _builtin_ocr_profiles(),
    },
}

IGNORED_SENDERS = {"team", "match"}
DEBUG_LEVEL = 2

_cached_config: dict[str, Any] | None = None
_cached_paths: "AppPaths | None" = None


@dataclass(frozen=True)
class AppPaths:
    log_dir: Path
    appdata_dir: Path
    config_path: Path
    chat_log: Path
    hero_log: Path
    crash_log: Path
    snap_dir: Path


class LazyConfig(Mapping[str, Any]):
    def _data(self) -> dict[str, Any]:
        return load_config()

    def __getitem__(self, key: str) -> Any:
        return self._data()[key]

    def __iter__(self) -> Iterator[str]:
        return iter(self._data())

    def __len__(self) -> int:
        return len(self._data())

    def __repr__(self) -> str:
        return repr(self._data())


def default_appdata_dir() -> Path:
    appdata = os.getenv("APPDATA")
    if appdata:
        return Path(appdata) / "ow-chat-logger"
    return Path.home() / ".ow-chat-logger"


def is_packaged_windows_run() -> bool:
    return sys.platform == "win32" and bool(getattr(sys, "frozen", False))


def default_runtime_base_dir() -> Path:
    if is_packaged_windows_run():
        return Path(sys.executable).resolve().parent
    return Path.cwd().resolve()


def default_runtime_log_dir() -> Path:
    return default_runtime_base_dir() / PACKAGED_OUTPUT_DIR_NAME


def get_user_config_path() -> Path:
    env_path = os.getenv("OW_CHAT_LOGGER_CONFIG")
    if env_path:
        return Path(os.path.expandvars(env_path)).expanduser()
    return default_appdata_dir() / "config.json"


def resolve_log_dir(path: str | Path) -> Path:
    """Expand %VAR% (e.g. %APPDATA%) and user home (~) in a log_dir string."""
    return Path(os.path.expandvars(str(path))).expanduser()


def _load_user_config() -> dict[str, Any]:
    cfg_path = get_user_config_path()
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


def _normalize_ocr_config(raw_config: dict[str, Any], user_data: dict[str, Any]) -> dict[str, Any]:
    normalized = deepcopy(raw_config)
    user_ocr = user_data.get("ocr") if isinstance(user_data.get("ocr"), dict) else {}
    normalized["ocr"] = _deep_merge_dict(_DEFAULT_CONFIG["ocr"], user_ocr)

    has_explicit_ocr_profiles = bool(user_ocr.get("profiles"))
    legacy_overrides = {key: deepcopy(user_data[key]) for key in LEGACY_OCR_FLAT_KEYS if key in user_data}
    if legacy_overrides and not has_explicit_ocr_profiles:
        default_profile = normalized["ocr"]["profiles"][DEFAULT_OCR_PROFILE]
        if "languages" in legacy_overrides:
            default_profile["languages"] = deepcopy(legacy_overrides["languages"])
        for key in PIPELINE_CONFIG_KEYS:
            if key in legacy_overrides:
                default_profile["pipeline"][key] = deepcopy(legacy_overrides[key])
        for key in ENGINE_SETTING_KEYS:
            if key in legacy_overrides:
                default_profile["settings"][key] = deepcopy(legacy_overrides[key])

    profile = resolve_ocr_profile(normalized)
    normalized.update(profile.pipeline)
    normalized["languages"] = list(profile.languages)
    normalized.update(profile.settings)
    normalized["ocr_default_profile"] = profile.name
    normalized["ocr_default_engine"] = profile.engine_id
    return normalized


def merge_runtime_config(overrides: dict[str, Any] | None = None, *, base: dict[str, Any] | None = None) -> dict[str, Any]:
    root = load_config() if base is None else deepcopy(base)
    if not overrides:
        return deepcopy(root)
    merged = _deep_merge_dict(root, overrides)
    return _normalize_ocr_config(merged, overrides)


def resolve_ocr_profile(
    config: dict[str, Any] | None = None,
    profile_name: str | None = None,
) -> ResolvedOCRProfile:
    cfg = load_config() if config is None else config
    ocr_cfg = cfg.get("ocr") or {}
    profiles = ocr_cfg.get("profiles") or {}
    chosen_name = profile_name or ocr_cfg.get("default_profile") or DEFAULT_OCR_PROFILE
    if chosen_name not in profiles:
        raise KeyError(f"Unknown OCR profile: {chosen_name}")
    raw_profile = profiles[chosen_name]
    pipeline = deepcopy(raw_profile.get("pipeline") or {})
    pipeline["screen_region"] = deepcopy(cfg.get("screen_region"))
    return ResolvedOCRProfile(
        name=chosen_name,
        engine_id=str(raw_profile.get("engine", "")),
        languages=list(raw_profile.get("languages") or ["en"]),
        pipeline=pipeline,
        settings=deepcopy(raw_profile.get("settings") or {}),
    )


def load_config(*, reload: bool = False) -> dict[str, Any]:
    global _cached_config
    if _cached_config is not None and not reload:
        return _cached_config

    user_data = _load_user_config()
    user_data_without_log_dir = {key: value for key, value in user_data.items() if key != "log_dir"}
    config = {**_DEFAULT_CONFIG, **user_data_without_log_dir}
    config["log_dir"] = str(default_runtime_log_dir())

    if env_dir := os.getenv("OW_CHAT_LOG_DIR"):
        config["log_dir"] = env_dir

    if isinstance(config.get("log_dir"), str):
        config["log_dir"] = os.path.expandvars(config["log_dir"])

    _cached_config = _normalize_ocr_config(config, user_data)
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
    appdata_dir = default_appdata_dir()
    paths = AppPaths(
        log_dir=log_dir,
        appdata_dir=appdata_dir,
        config_path=get_user_config_path(),
        chat_log=log_dir / "chat_log.csv",
        hero_log=log_dir / "hero_log.csv",
        crash_log=appdata_dir / "crash.log",
        snap_dir=log_dir / "debug_snaps",
    )
    if ensure_exists:
        paths.appdata_dir.mkdir(parents=True, exist_ok=True)
        paths.log_dir.mkdir(parents=True, exist_ok=True)
        paths.snap_dir.mkdir(parents=True, exist_ok=True)
    _cached_paths = paths
    return _cached_paths


def reset_paths() -> None:
    global _cached_paths
    _cached_paths = None


CONFIG = LazyConfig()
