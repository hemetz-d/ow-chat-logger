from __future__ import annotations

import asyncio
import inspect
from typing import Any

import numpy as np

from ow_chat_logger.ocr.base import BaseOCRBackend, OCRBackendUnavailableError, OCRResult


def _import_winrt_modules() -> dict[str, Any]:
    try:
        from winrt.windows.globalization import Language
        from winrt.windows.graphics.imaging import (
            BitmapPixelFormat,
            SoftwareBitmap,
        )
        from winrt.windows.media.ocr import OcrEngine as WinRTOcrEngine
        from winrt.windows.storage.streams import Buffer
    except ImportError as exc:  # pragma: no cover - depends on local runtime
        raise OCRBackendUnavailableError(
            "Windows OCR dependencies are not installed. "
            "Install the WinRT packages listed in requirements.txt."
        ) from exc

    return {
        "Language": Language,
        "BitmapPixelFormat": BitmapPixelFormat,
        "SoftwareBitmap": SoftwareBitmap,
        "WinRTOcrEngine": WinRTOcrEngine,
        "Buffer": Buffer,
    }


async def _await_once(awaitable):
    return await awaitable


def _await_async_operation(operation):
    if hasattr(operation, "get"):
        return operation.get()

    if inspect.isawaitable(operation):
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(_await_once(operation))
        raise RuntimeError("Windows OCR cannot run inside an active asyncio event loop.")

    return operation


def _normalize_language_candidates(languages) -> list[str]:
    ordered: list[str] = []
    for language in list(languages) + ["en"]:
        if language not in ordered:
            ordered.append(language)
    return ordered


def _rect_to_bbox(rect) -> list[list[float]]:
    left = float(rect.x)
    top = float(rect.y)
    right = left + float(rect.width)
    bottom = top + float(rect.height)
    return [
        [left, top],
        [right, top],
        [right, bottom],
        [left, bottom],
    ]


def _enum_member(enum_type, *names):
    for name in names:
        if hasattr(enum_type, name):
            return getattr(enum_type, name)
    raise AttributeError(f"Could not resolve any of {names!r} on {enum_type!r}")


def _call_static_method(target, names, *args, **kwargs):
    for name in names:
        method = getattr(target, name, None)
        if method is not None:
            if kwargs:
                try:
                    return method(**kwargs)
                except TypeError:
                    pass
            return method(*args)
    raise AttributeError(f"Could not resolve any of {names!r} on {target!r}")


class WindowsOCRBackend(BaseOCRBackend):
    engine_id = "windows"

    def __init__(self, profile):
        super().__init__(profile)
        self._winrt = _import_winrt_modules()
        self.language_tag, self.reader = self._create_reader(self.languages)

    def _create_reader(self, languages):
        language_cls = self._winrt["Language"]
        engine_cls = self._winrt["WinRTOcrEngine"]

        for language_tag in _normalize_language_candidates(languages):
            language = language_cls(language_tag)
            reader = _call_static_method(
                engine_cls,
                ("try_create_from_language", "TryCreateFromLanguage"),
                language,
            )
            if reader is not None:
                return language_tag, reader

        raise OCRBackendUnavailableError(
            "Windows OCR is unavailable for the requested languages. "
            "Package the app with Windows app identity and ensure the language pack is installed."
        )

    def _mask_to_software_bitmap(self, mask: np.ndarray):
        if mask.ndim != 2:
            raise ValueError("OCR mask must be a 2D grayscale image.")

        bitmap_cls = self._winrt["SoftwareBitmap"]
        pixel_format = _enum_member(self._winrt["BitmapPixelFormat"], "BGRA8", "Bgra8")
        height, width = mask.shape
        bgra = np.empty((height, width, 4), dtype=np.uint8)
        bgra[..., 0] = mask
        bgra[..., 1] = mask
        bgra[..., 2] = mask
        bgra[..., 3] = 255
        raw = bytes(bgra.reshape(-1))
        buffer = self._winrt["Buffer"](len(raw))
        buffer.length = len(raw)
        memoryview(buffer)[: len(raw)] = raw

        return _call_static_method(
            bitmap_cls,
            ("create_copy_from_buffer", "CreateCopyFromBuffer"),
            buffer,
            pixel_format,
            width,
            height,
        )

    @staticmethod
    def _recognized_words(result) -> list[Any]:
        words = []
        for line in getattr(result, "lines", []):
            words.extend(getattr(line, "words", []))
        return words

    def run(self, mask: np.ndarray) -> list[OCRResult]:
        software_bitmap = self._mask_to_software_bitmap(mask)
        recognize = getattr(self.reader, "recognize_async", None)
        if recognize is None:
            recognize = getattr(self.reader, "RecognizeAsync")
        result = _await_async_operation(recognize(software_bitmap))

        return [
            (_rect_to_bbox(word.bounding_rect), word.text, 1.0)
            for word in self._recognized_words(result)
            if getattr(word, "text", "").strip()
        ]
