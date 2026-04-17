"""Tests for config helpers (no full module reload)."""

import sys
from pathlib import Path

import pytest

from ow_chat_logger.config import CONFIG, resolve_log_dir
from ow_chat_logger.ocr import ResolvedOCRProfile


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


def test_resolved_ocr_profile_pipeline_and_settings_are_read_only():
    profile = ResolvedOCRProfile(
        name="n",
        engine_id="e",
        languages=["en"],
        pipeline={"scale_factor": 3},
        settings={"confidence_threshold": 0.7},
    )
    with pytest.raises(TypeError):
        profile.pipeline["scale_factor"] = 4
    with pytest.raises(TypeError):
        profile.settings["confidence_threshold"] = 0.9


def test_get_app_paths_uses_packaged_output_dir_on_frozen_windows(monkeypatch):
    import ow_chat_logger.config as cfg_module

    appdata = Path(__file__).resolve().parent / "_tmp_appdata_packaged"
    exe_dir = Path(__file__).resolve().parent / "_tmp_packaged_app"
    exe_dir.mkdir(parents=True, exist_ok=True)
    appdata.mkdir(parents=True, exist_ok=True)

    monkeypatch.setenv("APPDATA", str(appdata))
    monkeypatch.delenv("OW_CHAT_LOG_DIR", raising=False)
    monkeypatch.delenv("OW_CHAT_LOGGER_CONFIG", raising=False)
    monkeypatch.setattr(cfg_module.sys, "frozen", True, raising=False)
    monkeypatch.setattr(cfg_module.sys, "executable", str(exe_dir / "ow-chat-logger.exe"))

    cfg_module.reset_config()
    paths = cfg_module.get_app_paths()

    assert paths.log_dir == exe_dir / "OW Chat Logger Data"
    assert paths.chat_log == paths.log_dir / "chat_log.csv"
    assert paths.hero_log == paths.log_dir / "hero_log.csv"
    assert paths.snap_dir == paths.log_dir / "debug_snaps"
    assert paths.crash_log == appdata / "ow-chat-logger" / "crash.log"
    assert paths.config_path == appdata / "ow-chat-logger" / "config.json"


def test_get_app_paths_keeps_non_packaged_default_behavior(monkeypatch):
    import ow_chat_logger.config as cfg_module

    appdata = Path(__file__).resolve().parent / "_tmp_appdata_default"
    cwd = Path(__file__).resolve().parent / "_tmp_runtime_cwd_default"
    appdata.mkdir(parents=True, exist_ok=True)
    cwd.mkdir(parents=True, exist_ok=True)

    monkeypatch.setenv("APPDATA", str(appdata))
    monkeypatch.delenv("OW_CHAT_LOG_DIR", raising=False)
    monkeypatch.delenv("OW_CHAT_LOGGER_CONFIG", raising=False)
    monkeypatch.delattr(cfg_module.sys, "frozen", raising=False)
    monkeypatch.chdir(cwd)

    cfg_module.reset_config()
    paths = cfg_module.get_app_paths()

    assert paths.log_dir == cwd / "OW Chat Logger Data"
    assert paths.crash_log == appdata / "ow-chat-logger" / "crash.log"
    assert paths.config_path == appdata / "ow-chat-logger" / "config.json"


def test_config_log_dir_is_ignored_for_packaged_default(monkeypatch):
    import ow_chat_logger.config as cfg_module

    appdata = Path(__file__).resolve().parent / "_tmp_appdata_ignore_config_log_dir"
    config_dir = appdata / "ow-chat-logger"
    config_dir.mkdir(parents=True, exist_ok=True)
    custom_log_dir = Path(__file__).resolve().parent / "_tmp_custom_output"
    exe_dir = Path(__file__).resolve().parent / "_tmp_packaged_app_ignore_config_log_dir"
    exe_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setenv("APPDATA", str(appdata))
    monkeypatch.delenv("OW_CHAT_LOG_DIR", raising=False)
    monkeypatch.delenv("OW_CHAT_LOGGER_CONFIG", raising=False)
    monkeypatch.setattr(cfg_module.sys, "frozen", True, raising=False)
    monkeypatch.setattr(cfg_module.sys, "executable", str(exe_dir / "ow-chat-logger.exe"))
    (config_dir / "config.json").write_text(
        '{"log_dir": "' + str(custom_log_dir).replace("\\", "\\\\") + '"}',
        encoding="utf-8",
    )

    cfg_module.reset_config()
    paths = cfg_module.get_app_paths()

    assert paths.log_dir == exe_dir / "OW Chat Logger Data"
    assert paths.crash_log == appdata / "ow-chat-logger" / "crash.log"


def test_environment_log_dir_overrides_packaged_default(monkeypatch):
    import ow_chat_logger.config as cfg_module

    appdata = Path(__file__).resolve().parent / "_tmp_appdata_env_override"
    env_log_dir = Path(__file__).resolve().parent / "_tmp_env_output"
    exe_dir = Path(__file__).resolve().parent / "_tmp_packaged_app_env"
    appdata.mkdir(parents=True, exist_ok=True)
    exe_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setenv("APPDATA", str(appdata))
    monkeypatch.setenv("OW_CHAT_LOG_DIR", str(env_log_dir))
    monkeypatch.delenv("OW_CHAT_LOGGER_CONFIG", raising=False)
    monkeypatch.setattr(cfg_module.sys, "frozen", True, raising=False)
    monkeypatch.setattr(cfg_module.sys, "executable", str(exe_dir / "ow-chat-logger.exe"))

    cfg_module.reset_config()
    paths = cfg_module.get_app_paths()

    assert paths.log_dir == env_log_dir
    assert paths.chat_log == env_log_dir / "chat_log.csv"
    assert paths.crash_log == appdata / "ow-chat-logger" / "crash.log"


def test_packaged_runtime_filters_non_windows_ocr_profiles(monkeypatch):
    import ow_chat_logger.config as cfg_module

    appdata = Path(__file__).resolve().parent / "_tmp_appdata_packaged_profiles"
    config_dir = appdata / "ow-chat-logger"
    exe_dir = Path(__file__).resolve().parent / "_tmp_packaged_app_profiles"
    config_dir.mkdir(parents=True, exist_ok=True)
    exe_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setenv("APPDATA", str(appdata))
    monkeypatch.delenv("OW_CHAT_LOG_DIR", raising=False)
    monkeypatch.delenv("OW_CHAT_LOGGER_CONFIG", raising=False)
    monkeypatch.setattr(cfg_module.sys, "frozen", True, raising=False)
    monkeypatch.setattr(cfg_module.sys, "executable", str(exe_dir / "ow-chat-logger.exe"))
    (config_dir / "config.json").write_text(
        """
        {
          "ocr": {
            "default_profile": "easyocr_master_baseline",
            "profiles": {
              "easyocr_master_baseline": {
                "engine": "easyocr",
                "languages": ["en"],
                "pipeline": {},
                "settings": {}
              }
            }
          }
        }
        """,
        encoding="utf-8",
    )

    cfg_module.reset_config()
    config = cfg_module.load_config()

    assert config["ocr"]["default_profile"] == "windows_default"
    assert sorted(config["ocr"]["profiles"]) == ["windows_default"]
    assert cfg_module.resolve_ocr_profile(config).engine_id == "windows"
