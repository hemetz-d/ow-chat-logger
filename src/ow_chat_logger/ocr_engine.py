"""Backward-compatible Windows OCR exports.

Internal callers should use the profile-aware OCR registry instead.
"""

from ow_chat_logger.ocr.base import ResolvedOCRProfile
from ow_chat_logger.ocr import windows as _windows
from ow_chat_logger.ocr.windows import (
    WindowsOCRBackend,
    _await_async_operation,
)


def _import_winrt_modules():
    return _windows._import_winrt_modules()


class OCREngine(WindowsOCRBackend):
    def __init__(self, languages):
        original = _windows._import_winrt_modules
        _windows._import_winrt_modules = _import_winrt_modules
        try:
            super().__init__(
                ResolvedOCRProfile(
                    name="legacy_windows",
                    engine_id="windows",
                    languages=list(languages),
                    pipeline={},
                    settings={},
                )
            )
        finally:
            _windows._import_winrt_modules = original


__all__ = ["OCREngine", "_await_async_operation", "_import_winrt_modules"]
