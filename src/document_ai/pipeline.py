"""
Document AI Pipeline Orchestrator.
Coordinates the end-to-end processing flow:
Ingestion -> Text Extraction & OCR -> Classification -> Field & Table Extraction ->
Normalization -> Business Validation -> Structured Result Assembly.
"""

from pathlib import Path
from typing import BinaryIO, Callable, List, Optional, Tuple, Union
import uuid

from PIL import Image

from document_ai.config import get_settings
from document_ai.document_classifier import classify_document
from document_ai.exceptions import DocumentAIError
from document_ai.field_extractor import extract_invoice_fields
from document_ai.ingestion import temporary_upload_file, validate_file
from document_ai.logging_config import get_logger
from document_ai.pdf_processor import extract_from_image, extract_from_pdf
from document_ai.schemas import (
    DocumentClassification,
    DocumentMetadata,
    DocumentResult,
    DocumentType,
    ExtractionMethod,
    PageExtraction,
    ProcessingStatus,
    ValidationResult,
)
from document_ai.table_extractor import extract_table_items
from document_ai.validator import validate_invoice

logger = get_logger("pipeline")


class DocumentProcessingPipeline:
    """End-to-end document processing pipeline."""

    def __init__(self) -> None:
        self.settings = get_settings()

    def process_file(
        self,
        file_source: Union[Path, BinaryIO, bytes],
        filename: str,
        force_invoice_parsing: bool = False,
    ) -> Tuple[DocumentResult, List[Image.Image]]:
        """
        Executes end-to-end document processing for a single document.
        Returns the structured DocumentResult and rendered page PIL images.
        """
        doc_id = str(uuid.uuid4())
        logger.info(f"Starting processing for '{filename}' [Doc ID: {doc_id}]")

        # Step 1: Ingestion & Validation
        with temporary_upload_file(file_source, filename) as (temp_path, metadata):
            return self._process_temp_file(
                doc_id=doc_id,
                temp_path=temp_path,
                metadata=metadata,
                force_invoice_parsing=force_invoice_parsing,
            )

    def _process_temp_file(
        self,
        doc_id: str,
        temp_path: Path,
        metadata: DocumentMetadata,
        force_invoice_parsing: bool = False,
    ) -> Tuple[DocumentResult, List[Image.Image]]:
        pages: List[PageExtraction] = []
        page_images: List[Image.Image] = []
        errors: List[str] = []

        # Step 2: Extraction (Digital PDF or Image OCR)
        try:
            if metadata.file_type == "pdf":
                pages, page_images = extract_from_pdf(temp_path)
            else:
                pages, page_images = extract_from_image(temp_path)
            metadata.page_count = len(pages)
        except Exception as e:
            logger.error(f"Extraction failed for {metadata.filename}: {e}")
            errors.append(f"Extraction error: {str(e)}")
            dummy_class = DocumentClassification(
                predicted_type=DocumentType.UNKNOWN,
                confidence=0.0,
                evidence=[],
                requires_human_review=True,
            )
            return (
                DocumentResult(
                    document_id=doc_id,
                    filename=metadata.filename,
                    metadata=metadata,
                    classification=dummy_class,
                    extraction_method=ExtractionMethod.UNPROCESSED.value,
                    pages=[],
                    status=ProcessingStatus.FAILED,
                    errors=errors,
                ),
                [],
            )

        # Determine overall extraction method
        if all(p.extraction_method == ExtractionMethod.DIGITAL_PDF.value for p in pages):
            overall_method = ExtractionMethod.DIGITAL_PDF.value
        elif any(p.ocr_applied for p in pages):
            overall_method = ExtractionMethod.OCR_TESSERACT.value if metadata.file_type == "pdf" else ExtractionMethod.IMAGE_OCR.value
        else:
            overall_method = ExtractionMethod.HYBRID.value

        # Step 3: Classification
        classification = classify_document(pages)
        logger.info(
            f"Classified '{metadata.filename}' as '{classification.predicted_type.value}' "
            f"(Confidence: {classification.confidence:.2f})"
        )

        # Step 4: Invoice Field & Table Extraction (if Invoice or forced)
        is_invoice = (classification.predicted_type == DocumentType.INVOICE) or force_invoice_parsing
        invoice_data = None
        line_items = []
        validation = ValidationResult()

        if is_invoice:
            invoice_data = extract_invoice_fields(pages)
            line_items = extract_table_items(pages)
            # Step 5: Validation
            validation = validate_invoice(invoice_data, line_items)
            logger.info(
                f"Validation for '{metadata.filename}': "
                f"Valid={validation.is_valid}, Errors={validation.error_count}, Warnings={validation.warning_count}"
            )

        # Step 6: Determine overall processing status
        if not pages or any(p.error for p in pages):
            if any("OCR is not installed" in (p.error or "") for p in pages):
                status = ProcessingStatus.WARNINGS
            else:
                status = ProcessingStatus.FAILED if not pages else ProcessingStatus.WARNINGS
        elif validation.error_count > 0 or classification.requires_human_review:
            status = ProcessingStatus.REVIEW_REQUIRED
        elif validation.warning_count > 0:
            status = ProcessingStatus.WARNINGS
        else:
            status = ProcessingStatus.SUCCESS

        result = DocumentResult(
            document_id=doc_id,
            filename=metadata.filename,
            metadata=metadata,
            classification=classification,
            extraction_method=overall_method,
            pages=pages,
            invoice_data=invoice_data,
            line_items=line_items,
            validation=validation,
            status=status,
            errors=errors,
        )

        return result, page_images

    def process_batch(
        self,
        files: List[Tuple[Union[Path, BinaryIO, bytes], str]],
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
    ) -> List[DocumentResult]:
        """
        Processes a batch of files sequentially and safely.
        One document error will never cause the batch to crash.
        """
        results: List[DocumentResult] = []
        total = len(files)

        for idx, (source, fname) in enumerate(files, start=1):
            if progress_callback:
                progress_callback(idx, total, fname)

            try:
                res, _ = self.process_file(source, fname)
                results.append(res)
            except Exception as e:
                logger.error(f"Batch processing error on '{fname}': {e}")
                err_res = DocumentResult(
                    document_id=str(uuid.uuid4()),
                    filename=fname,
                    metadata=DocumentMetadata(
                        filename=fname,
                        file_type="unknown",
                        file_size_bytes=0,
                        page_count=0,
                        created_at="",
                        checksum_sha256="",
                    ),
                    classification=DocumentClassification(
                        predicted_type=DocumentType.UNKNOWN,
                        confidence=0.0,
                    ),
                    extraction_method=ExtractionMethod.UNPROCESSED.value,
                    status=ProcessingStatus.FAILED,
                    errors=[f"Batch processing unhandled error: {str(e)}"],
                )
                results.append(err_res)

        return results


_PIPELINE = DocumentProcessingPipeline()


def get_pipeline() -> DocumentProcessingPipeline:
    """Retrieve singleton document processing pipeline."""
    return _PIPELINE
