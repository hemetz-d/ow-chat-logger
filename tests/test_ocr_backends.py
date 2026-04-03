from __future__ import annotations

from types import SimpleNamespace

import numpy as np

from ow_chat_logger.config import merge_runtime_config, resolve_ocr_profile
from ow_chat_logger.ocr.easyocr_backend import EasyOCRBackend
from ow_chat_logger.ocr.tesseract_backend import TesseractOCRBackend


def test_resolve_ocr_profile_uses_windows_default_profile():
    config = merge_runtime_config()

    profile = resolve_ocr_profile(config)

    assert profile.name == "windows_default"
    assert profile.engine_id == "windows"
    assert profile.pipeline["scale_factor"] == 4


def test_merge_runtime_config_maps_legacy_flat_overrides_to_default_profile():
    config = merge_runtime_config({"scale_factor": 7, "languages": ["de"]})
    profile = resolve_ocr_profile(config)

    assert profile.pipeline["scale_factor"] == 7
    assert profile.languages == ["de"]


def test_easyocr_backend_filters_by_confidence(monkeypatch):
    class FakeReader:
        def readtext(self, mask, **kwargs):
            return [
                ([[0, 0], [1, 0], [1, 1], [0, 1]], "keep", 0.9),
                ([[0, 0], [1, 0], [1, 1], [0, 1]], "drop", 0.1),
            ]

    fake_easyocr = SimpleNamespace(Reader=lambda languages, gpu=False: FakeReader())
    monkeypatch.setitem(__import__("sys").modules, "easyocr", fake_easyocr)

    profile = resolve_ocr_profile(merge_runtime_config(), "easyocr_master_baseline")
    backend = EasyOCRBackend(profile)

    assert backend.run(np.zeros((2, 2), dtype=np.uint8)) == [
        ([[0, 0], [1, 0], [1, 1], [0, 1]], "keep", 0.9)
    ]


def test_tesseract_backend_returns_boxes_and_confidence(monkeypatch):
    class FakePytesseract:
        class TesseractNotFoundError(RuntimeError):
            pass

        pytesseract = SimpleNamespace(tesseract_cmd="")

        @staticmethod
        def image_to_data(mask, lang=None, config=None, output_type=None):
            return {
                "text": ["keep", ""],
                "conf": ["95", "-1"],
                "left": [1, 0],
                "top": [2, 0],
                "width": [3, 0],
                "height": [4, 0],
            }

    monkeypatch.setitem(
        __import__("sys").modules,
        "pytesseract",
        SimpleNamespace(
            image_to_data=FakePytesseract.image_to_data,
            pytesseract=FakePytesseract.pytesseract,
            Output=SimpleNamespace(DICT="DICT"),
            TesseractNotFoundError=FakePytesseract.TesseractNotFoundError,
        ),
    )

    profile = resolve_ocr_profile(merge_runtime_config(), "tesseract_default")
    backend = TesseractOCRBackend(profile)

    assert backend.run(np.zeros((2, 2), dtype=np.uint8)) == [
        ([[1.0, 2.0], [4.0, 2.0], [4.0, 6.0], [1.0, 6.0]], "keep", 95.0)
    ]
