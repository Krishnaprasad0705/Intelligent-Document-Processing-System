"""
Document AI - Intelligent Document Processing (IDP) System
Production-grade modular document processing engine.
"""

__version__ = "1.0.0"

from document_ai.config import get_settings
from document_ai.pipeline import DocumentProcessingPipeline
from document_ai.schemas import DocumentResult, DocumentType, ExtractionMethod

__all__ = [
    "get_settings",
    "DocumentProcessingPipeline",
    "DocumentResult",
    "DocumentType",
    "ExtractionMethod",
]
