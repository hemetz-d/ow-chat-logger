from __future__ import annotations

from typing import Callable

from ow_chat_logger.ocr.base import OCRBackend, ResolvedOCRProfile
from ow_chat_logger.ocr.easyocr_backend import EasyOCRBackend
from ow_chat_logger.ocr.tesseract_backend import TesseractOCRBackend
from ow_chat_logger.ocr.windows import WindowsOCRBackend

BackendBuilder = Callable[[ResolvedOCRProfile], OCRBackend]

_BACKENDS: dict[str, BackendBuilder] = {
    "windows": WindowsOCRBackend,
    "easyocr": EasyOCRBackend,
    "tesseract": TesseractOCRBackend,
}


def registered_backend_ids() -> list[str]:
    return sorted(_BACKENDS)


def build_ocr_backend(profile: ResolvedOCRProfile) -> OCRBackend:
    try:
        builder = _BACKENDS[profile.engine_id]
    except KeyError as exc:
        raise ValueError(f"Unknown OCR engine: {profile.engine_id}") from exc
    return builder(profile)
