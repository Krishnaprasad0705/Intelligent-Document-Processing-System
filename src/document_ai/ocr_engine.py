"""
OCR Engine Interface.
Provides safe abstraction over Tesseract OCR with graceful fallback,
detailed diagnostics, and guidance when external OCR executables are missing.
"""

from pathlib import Path
import shutil
from typing import Dict, Optional, Tuple
from PIL import Image
import pytesseract

from document_ai.config import get_settings
from document_ai.exceptions import OCRUnavailableError
from document_ai.logging_config import get_logger

logger = get_logger("ocr_engine")


class OCREngine:
    """Encapsulates OCR engine operations with availability detection."""

    def __init__(self) -> None:
        self.settings = get_settings()
        self._tesseract_path: Optional[str] = None
        self._is_available: Optional[bool] = None
        self._detect_engine()

    def _detect_engine(self) -> None:
        """Determines if the Tesseract binary is accessible."""
        # 1. Check explicit setting
        if self.settings.tesseract_cmd and Path(self.settings.tesseract_cmd).is_file():
            self._tesseract_path = self.settings.tesseract_cmd
            pytesseract.pytesseract.tesseract_cmd = self._tesseract_path
            self._is_available = True
            logger.info(f"Using explicitly configured Tesseract: {self._tesseract_path}")
            return

        # 2. Check standard system PATH
        which_path = shutil.which("tesseract")
        if which_path:
            self._tesseract_path = which_path
            pytesseract.pytesseract.tesseract_cmd = which_path
            self._is_available = True
            logger.info(f"Found Tesseract on PATH: {which_path}")
            return

        # 3. Check common Windows default directories
        common_windows_paths = [
            r"C:\Program Files\Tesseract-OCR\tesseract.exe",
            r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
            str(Path.home() / "AppData" / "Local" / "Programs" / "Tesseract-OCR" / "tesseract.exe"),
        ]
        for p in common_windows_paths:
            if Path(p).is_file():
                self._tesseract_path = p
                pytesseract.pytesseract.tesseract_cmd = p
                self._is_available = True
                logger.info(f"Found Tesseract in default path: {p}")
                return

        self._is_available = False
        logger.info("Tesseract binary not found on system. OCR will be disabled.")

    @property
    def is_available(self) -> bool:
        """Returns True if Tesseract OCR is installed and ready."""
        if self._is_available is None:
            self._detect_engine()
        return bool(self._is_available)

    def get_status_info(self) -> Dict[str, str]:
        """Returns diagnostic information and installation instructions."""
        if self.is_available:
            return {
                "available": "true",
                "binary_path": str(self._tesseract_path),
                "message": "Tesseract OCR engine is active and ready."
            }
        return {
            "available": "false",
            "binary_path": "Not found",
            "message": (
                "Tesseract OCR executable is not installed or not in PATH. "
                "Digital PDFs will still be processed with direct text extraction. "
                "To enable OCR on scanned images/PDFs on Windows, install Tesseract from: "
                "https://github.com/UB-Mannheim/tesseract/wiki and set TESSERACT_CMD in .env"
            )
        }

    def extract_text_from_image(self, img: Image.Image) -> Tuple[str, float]:
        """
        Runs OCR on given PIL image.
        Returns (extracted_text, confidence_score).
        Raises OCRUnavailableError if Tesseract is not installed.
        """
        if not self.is_available:
            raise OCRUnavailableError(
                "Cannot perform OCR: Tesseract binary is not installed on this system. "
                "Please install Tesseract OCR or upload a digital PDF."
            )

        try:
            # Primary pass with PSM 6 (uniform block / structured invoice layout)
            config_primary = "--oem 1 --psm 6"
            full_text = pytesseract.image_to_string(img, config=config_primary).strip()

            # Fallback to PSM 3 if PSM 6 produced minimal output
            if len(full_text) < 25:
                full_text = pytesseract.image_to_string(img, config="--oem 1 --psm 3").strip()

            # Extract confidence statistics
            try:
                data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT, config=config_primary)
                confidences = [
                    float(c) for c in data.get("conf", [])
                    if c is not None and str(c).strip() != "" and float(c) >= 0
                ]
                avg_conf = (sum(confidences) / len(confidences) / 100.0) if confidences else 0.85
            except Exception:
                avg_conf = 0.85

            return full_text.strip(), round(avg_conf, 2)

        except Exception as e:
            logger.error(f"OCR execution failed: {e}")
            raise OCRUnavailableError(f"Tesseract OCR processing failed: {str(e)}")


_OCR_ENGINE_INSTANCE: Optional[OCREngine] = None


def get_ocr_engine() -> OCREngine:
    """Retrieve singleton OCR engine instance."""
    global _OCR_ENGINE_INSTANCE
    if _OCR_ENGINE_INSTANCE is None:
        _OCR_ENGINE_INSTANCE = OCREngine()
    return _OCR_ENGINE_INSTANCE
