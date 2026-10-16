"""
Exception hierarchy for Document AI.
Distinguishes between user-correctable errors, file format errors,
OCR failures, and system exceptions.
"""

from typing import Optional


class DocumentAIError(Exception):
    """Base exception for all Document AI errors."""
    def __init__(self, message: str, details: Optional[dict] = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


class IngestionError(DocumentAIError):
    """Raised when document ingestion or preliminary validation fails."""
    pass


class UnsupportedFileTypeError(IngestionError):
    """Raised when an uploaded file is not among supported extensions or mime types."""
    pass


class FileSizeLimitError(IngestionError):
    """Raised when an uploaded file exceeds the configured maximum size."""
    pass


class CorruptedFileError(IngestionError):
    """Raised when a file cannot be parsed or opened because it is corrupt or empty."""
    pass


class ExtractionError(DocumentAIError):
    """Raised when text extraction fails completely."""
    pass


class OCRError(ExtractionError):
    """Raised when an OCR engine operation fails or is unavailable."""
    pass


class OCRUnavailableError(OCRError):
    """Raised when Tesseract OCR is requested/required but binary is not installed."""
    pass


class ClassificationError(DocumentAIError):
    """Raised when document classification encounters an unrecoverable failure."""
    pass


class ParsingError(DocumentAIError):
    """Raised when table or field extraction fails."""
    pass


class ValidationError(DocumentAIError):
    """Raised when document schema or business validation encounters a fatal error."""
    pass


class ExportError(DocumentAIError):
    """Raised when structured data serialization to disk or stream fails."""
    pass
