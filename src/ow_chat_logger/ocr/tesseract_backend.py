from __future__ import annotations

from typing import Any

import numpy as np

from ow_chat_logger.ocr.base import BaseOCRBackend, OCRBackendUnavailableError, OCRResult


def _rect_to_bbox(left: float, top: float, width: float, height: float) -> list[list[float]]:
    right = left + width
    bottom = top + height
    return [
        [left, top],
        [right, top],
        [right, bottom],
        [left, bottom],
    ]


class TesseractOCRBackend(BaseOCRBackend):
    engine_id = "tesseract"

    def __init__(self, profile):
        super().__init__(profile)
        try:
            import pytesseract
            from pytesseract import Output
        except ImportError as exc:  # pragma: no cover - optional dependency
            raise OCRBackendUnavailableError(
                "pytesseract is not installed. Install the tesseract extra to enable this profile."
            ) from exc

        self._pytesseract = pytesseract
        self._output = Output
        self.confidence_threshold = float(self.settings.get("confidence_threshold", 0.0))
        self.psm = self.settings.get("psm")
        self.oem = self.settings.get("oem")
        self.allowlist = self.settings.get("allowlist")
        self.extra_config = str(self.settings.get("extra_config", "")).strip()
        executable = str(self.settings.get("executable_path", "")).strip()
        if executable:
            self._pytesseract.pytesseract.tesseract_cmd = executable

    def _language_arg(self) -> str:
        explicit = str(self.settings.get("language", "")).strip()
        if explicit:
            return explicit
        return "+".join(self.languages)

    def _config_string(self) -> str:
        parts: list[str] = []
        if self.oem is not None:
            parts.extend(["--oem", str(self.oem)])
        if self.psm is not None:
            parts.extend(["--psm", str(self.psm)])
        if self.allowlist:
            parts.extend(["-c", f"tessedit_char_whitelist={self.allowlist}"])
        if self.extra_config:
            parts.append(self.extra_config)
        return " ".join(parts).strip()

    def run(self, mask: np.ndarray) -> list[OCRResult]:
        try:
            data: dict[str, list[Any]] = self._pytesseract.image_to_data(
                mask,
                lang=self._language_arg(),
                config=self._config_string(),
                output_type=self._output.DICT,
            )
        except self._pytesseract.TesseractNotFoundError as exc:  # pragma: no cover - local runtime
            raise OCRBackendUnavailableError(
                "Tesseract executable was not found. Install Tesseract and configure executable_path."
            ) from exc

        out: list[OCRResult] = []
        for idx, text in enumerate(data.get("text", [])):
            text = str(text).strip()
            if not text:
                continue
            conf_raw = str(data.get("conf", [""])[idx]).strip()
            try:
                conf = float(conf_raw)
            except ValueError:
                conf = -1.0
            if conf < self.confidence_threshold:
                continue

            left = float(data["left"][idx])
            top = float(data["top"][idx])
            width = float(data["width"][idx])
            height = float(data["height"][idx])
            out.append((_rect_to_bbox(left, top, width, height), text, conf))
        return out
