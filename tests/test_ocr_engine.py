from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pytest

from ow_chat_logger.ocr_engine import OCREngine, _await_async_operation


class FakeAsyncResult:
    def __init__(self, value):
        self._value = value

    def get(self):
        return self._value


class FakeSoftwareBitmap:
    captured = None

    @staticmethod
    def create_copy_from_buffer(buffer, pixel_format, width, height):
        FakeSoftwareBitmap.captured = {
            "buffer": bytes(buffer),
            "pixel_format": pixel_format,
            "width": width,
            "height": height,
        }
        return "bitmap"


class FakeBuffer(bytearray):
    def __new__(cls, size):
        obj = super().__new__(cls, size)
        obj.length = 0
        return obj


class FakeWord:
    def __init__(self, text, rect):
        self.text = text
        self.bounding_rect = rect


class FakeLine:
    def __init__(self, *words):
        self.words = list(words)


class FakeReader:
    def __init__(self, tag):
        self.tag = tag

    def recognize_async(self, bitmap):
        assert bitmap == "bitmap"
        return FakeAsyncResult(
            SimpleNamespace(
                lines=[
                    FakeLine(
                        FakeWord("Hello", SimpleNamespace(x=1, y=2, width=3, height=4)),
                        FakeWord("world", SimpleNamespace(x=10, y=20, width=30, height=40)),
                    )
                ]
            )
        )


class FakeWinRTOcrEngine:
    @staticmethod
    def try_create_from_language(language):
        if language.tag == "de":
            return None
        if language.tag == "en":
            return FakeReader(language.tag)
        return None


class FakeLanguage:
    def __init__(self, tag):
        self.tag = tag


def test_await_async_operation_supports_get():
    assert _await_async_operation(FakeAsyncResult("done")) == "done"


def test_ocr_engine_falls_back_to_english(monkeypatch):
    monkeypatch.setattr(
        "ow_chat_logger.ocr.windows._import_winrt_modules",
        lambda: {
            "Language": FakeLanguage,
            "BitmapPixelFormat": SimpleNamespace(BGRA8="bgra8"),
            "SoftwareBitmap": FakeSoftwareBitmap,
            "WinRTOcrEngine": FakeWinRTOcrEngine,
            "Buffer": FakeBuffer,
        },
    )

    engine = OCREngine(["de"])

    assert engine.language_tag == "en"


def test_ocr_engine_run_returns_word_boxes(monkeypatch):
    monkeypatch.setattr(
        "ow_chat_logger.ocr.windows._import_winrt_modules",
        lambda: {
            "Language": FakeLanguage,
            "BitmapPixelFormat": SimpleNamespace(BGRA8="bgra8"),
            "SoftwareBitmap": FakeSoftwareBitmap,
            "WinRTOcrEngine": FakeWinRTOcrEngine,
            "Buffer": FakeBuffer,
        },
    )

    mask = np.array([[0, 255], [128, 64]], dtype=np.uint8)
    engine = OCREngine(["en"])

    results = engine.run(mask)

    assert results == [
        ([[1.0, 2.0], [4.0, 2.0], [4.0, 6.0], [1.0, 6.0]], "Hello", 1.0),
        ([[10.0, 20.0], [40.0, 20.0], [40.0, 60.0], [10.0, 60.0]], "world", 1.0),
    ]
    assert FakeSoftwareBitmap.captured["width"] == 2
    assert FakeSoftwareBitmap.captured["height"] == 2
    assert len(FakeSoftwareBitmap.captured["buffer"]) == 16


def test_ocr_engine_requires_2d_mask(monkeypatch):
    monkeypatch.setattr(
        "ow_chat_logger.ocr.windows._import_winrt_modules",
        lambda: {
            "Language": FakeLanguage,
            "BitmapPixelFormat": SimpleNamespace(BGRA8="bgra8"),
            "SoftwareBitmap": FakeSoftwareBitmap,
            "WinRTOcrEngine": FakeWinRTOcrEngine,
            "Buffer": FakeBuffer,
        },
    )

    engine = OCREngine(["en"])

    with pytest.raises(ValueError):
        engine.run(np.zeros((1, 1, 3), dtype=np.uint8))
