from __future__ import annotations

from pathlib import Path
from typing import Protocol

from app.config import settings


class OCRClient(Protocol):
    name: str

    def extract_text(self, path: str | Path) -> str:
        """Extract text from an image or scanned document."""


class DisabledOCRClient:
    name = "disabled"

    def extract_text(self, path: str | Path) -> str:
        raise RuntimeError("OCR client is not configured")


class PaddleOCRClient:
    name = "paddleocr"

    def __init__(self) -> None:
        try:
            from paddleocr import PaddleOCR
        except ImportError as exc:
            raise RuntimeError("paddleocr is not installed") from exc
        self.ocr = PaddleOCR(use_angle_cls=True, lang="ch")

    def extract_text(self, path: str | Path) -> str:
        result = self.ocr.ocr(str(path), cls=True)
        lines: list[str] = []
        for page in result or []:
            for item in page or []:
                if len(item) >= 2 and item[1]:
                    lines.append(str(item[1][0]))
        return "\n".join(lines)


def create_ocr_client() -> OCRClient:
    if settings.ocr_provider == "paddleocr":
        return PaddleOCRClient()
    return DisabledOCRClient()


ocr_client = create_ocr_client()
