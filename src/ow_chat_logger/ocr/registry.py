from __future__ import annotations

import importlib
from typing import Callable

from ow_chat_logger.ocr.base import OCRBackend, ResolvedOCRProfile

BackendBuilder = Callable[[ResolvedOCRProfile], OCRBackend]

_BACKEND_SPECS: dict[str, tuple[str, str]] = {
    "windows": ("ow_chat_logger.ocr.windows", "WindowsOCRBackend"),
    "easyocr": ("ow_chat_logger.ocr.easyocr_backend", "EasyOCRBackend"),
    "tesseract": ("ow_chat_logger.ocr.tesseract_backend", "TesseractOCRBackend"),
}


def registered_backend_ids() -> list[str]:
    return sorted(_BACKEND_SPECS)


def _load_backend_builder(engine_id: str) -> BackendBuilder:
    try:
        module_name, builder_name = _BACKEND_SPECS[engine_id]
    except KeyError as exc:
        raise ValueError(f"Unknown OCR engine: {engine_id}") from exc

    module = importlib.import_module(module_name)
    return getattr(module, builder_name)


def build_ocr_backend(profile: ResolvedOCRProfile) -> OCRBackend:
    builder = _load_backend_builder(profile.engine_id)
    return builder(profile)
