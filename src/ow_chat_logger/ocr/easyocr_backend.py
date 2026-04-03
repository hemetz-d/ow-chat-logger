from __future__ import annotations

import numpy as np

from ow_chat_logger.ocr.base import BaseOCRBackend, OCRBackendUnavailableError, OCRResult

DEFAULT_ALLOWLIST = (
    "abcdefghijklmnopqrstuvwxyz"
    "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    "0123456789"
    '# :[]*!?.,-üäöÜÄÖ+#()&%$§"='
)


class EasyOCRBackend(BaseOCRBackend):
    engine_id = "easyocr"

    def __init__(self, profile):
        super().__init__(profile)
        try:
            import easyocr
        except ImportError as exc:  # pragma: no cover - optional dependency
            raise OCRBackendUnavailableError(
                "EasyOCR is not installed. Install the easyocr extra to enable this profile."
            ) from exc

        self._easyocr = easyocr
        self.confidence_threshold = float(self.settings.get("confidence_threshold", 0.7))
        self.text_threshold = float(self.settings.get("text_threshold", 0.5))
        self.allowlist = str(self.settings.get("allowlist", DEFAULT_ALLOWLIST))
        self.use_gpu = bool(self.settings.get("use_gpu", True))
        self.reader = self._create_reader(self.languages, self.use_gpu)

    def _create_reader(self, languages, use_gpu):
        if not use_gpu:
            return self._easyocr.Reader(languages, gpu=False)
        try:
            return self._easyocr.Reader(languages, gpu=True)
        except Exception:
            return self._easyocr.Reader(languages, gpu=False)

    def run(self, mask: np.ndarray) -> list[OCRResult]:
        results = self.reader.readtext(
            mask,
            detail=1,
            paragraph=False,
            text_threshold=self.text_threshold,
            allowlist=self.allowlist,
        )
        return [
            (bbox, text, float(conf))
            for (bbox, text, conf) in results
            if str(text).strip() and float(conf) > self.confidence_threshold
        ]
