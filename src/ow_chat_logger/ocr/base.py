from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Protocol, TypeAlias

import numpy as np

BBox: TypeAlias = list[list[float]]
OCRResult: TypeAlias = tuple[BBox, str, float | None]


class OCRBackendError(RuntimeError):
    """Base error for OCR backend failures."""


class OCRBackendUnavailableError(OCRBackendError):
    """Raised when an optional OCR backend is not installed or configured."""


@dataclass(frozen=True)
class ResolvedOCRProfile:
    name: str
    engine_id: str
    languages: list[str]
    pipeline: dict[str, Any]
    settings: dict[str, Any]


class OCRBackend(Protocol):
    engine_id: str
    profile_name: str
    languages: list[str]

    def run(self, mask: np.ndarray) -> list[OCRResult]:
        ...


class BaseOCRBackend(ABC):
    engine_id = ""

    def __init__(self, profile: ResolvedOCRProfile):
        self.profile_name = profile.name
        self.languages = list(profile.languages)
        self.settings = dict(profile.settings)

    @abstractmethod
    def run(self, mask: np.ndarray) -> list[OCRResult]:
        raise NotImplementedError
