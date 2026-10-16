"""
Application configuration for Document AI.
Centralizes configuration parameters with sensible defaults and environment overrides.
"""

from dataclasses import dataclass, field
import os
from pathlib import Path
from typing import List, Optional
from dotenv import load_dotenv

# Load local environment variables if available
load_dotenv()


@dataclass
class DocumentAISettings:
    """Configuration settings for Document AI pipeline."""
    # Ingestion constraints
    max_upload_size_mb: int = int(os.getenv("MAX_UPLOAD_SIZE_MB", "25"))
    allowed_extensions: List[str] = field(
        default_factory=lambda: [".pdf", ".png", ".jpg", ".jpeg"]
    )
    max_pdf_pages: int = int(os.getenv("MAX_PDF_PAGES", "50"))
    
    # Text Extraction & OCR
    ocr_dpi: int = int(os.getenv("OCR_DPI", "300"))
    min_digital_text_chars: int = int(os.getenv("MIN_DIGITAL_TEXT_CHARS", "30"))
    tesseract_cmd: Optional[str] = os.getenv("TESSERACT_CMD", None)
    
    # Validation Tolerances
    rounding_tolerance: float = float(os.getenv("ROUNDING_TOLERANCE", "0.05"))
    
    # Data Storage Paths
    base_dir: Path = Path(__file__).resolve().parent.parent.parent
    temp_dir: Path = base_dir / "data" / "temp"
    export_dir: Path = base_dir / "data" / "exports"
    
    # Logging
    log_level: str = os.getenv("LOG_LEVEL", "INFO")
    
    def __post_init__(self) -> None:
        """Ensure directories exist."""
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        self.export_dir.mkdir(parents=True, exist_ok=True)


# Global singleton settings cache
_SETTINGS: Optional[DocumentAISettings] = None


def get_settings() -> DocumentAISettings:
    """Retrieve application settings instance."""
    global _SETTINGS
    if _SETTINGS is None:
        _SETTINGS = DocumentAISettings()
    return _SETTINGS


def reset_settings() -> DocumentAISettings:
    """Reset configuration settings instance (useful for testing)."""
    global _SETTINGS
    _SETTINGS = DocumentAISettings()
    return _SETTINGS
