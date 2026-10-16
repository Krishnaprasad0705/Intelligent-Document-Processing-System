"""
Document Text Extraction Layer.
Extracts embedded digital text from PDFs using PyMuPDF, detects scanned pages,
renders pages to PIL images for previews or OCR fallback, and handles raw image uploads.
"""

from io import BytesIO
from pathlib import Path
from typing import List, Tuple
import pymupdf
from PIL import Image

from document_ai.config import get_settings
from document_ai.exceptions import CorruptedFileError, ExtractionError
from document_ai.image_preprocessor import preprocess_for_ocr
from document_ai.logging_config import get_logger
from document_ai.ocr_engine import get_ocr_engine
from document_ai.schemas import ExtractionMethod, PageExtraction

logger = get_logger("pdf_processor")


def extract_from_pdf(pdf_path: Path) -> Tuple[List[PageExtraction], List[Image.Image]]:
    """
    Extracts text and renders page images from a PDF file.
    Uses a hybrid approach:
    - Direct digital text extraction first.
    - Scanned page detection with optional OCR fallback.
    - Never fabricates text for failed pages.
    """
    settings = get_settings()
    ocr = get_ocr_engine()

    try:
        doc = pymupdf.open(str(pdf_path))
    except Exception as e:
        raise CorruptedFileError(f"Failed to open PDF document '{pdf_path.name}': {str(e)}")

    page_count = len(doc)
    if page_count == 0:
        doc.close()
        raise CorruptedFileError(f"PDF document '{pdf_path.name}' contains no pages.")

    if page_count > settings.max_pdf_pages:
        logger.warning(
            f"Document has {page_count} pages, exceeding limit of {settings.max_pdf_pages}. "
            f"Processing first {settings.max_pdf_pages} pages."
        )
        page_count = settings.max_pdf_pages

    extractions: List[PageExtraction] = []
    page_images: List[Image.Image] = []

    zoom = settings.ocr_dpi / 72.0
    mat = pymupdf.Matrix(zoom, zoom)

    for page_idx in range(page_count):
        page_num = page_idx + 1
        page = doc.load_page(page_idx)

        # 1. Direct digital text extraction with 2D visual layout sorting
        digital_text = page.get_text("text", sort=True).strip()
        
        # Render page pixmap to PIL Image
        pix = page.get_pixmap(matrix=mat, alpha=False)
        img = Image.open(BytesIO(pix.tobytes("png")))
        page_images.append(img)

        # 2. Check if digital text is sufficient
        if len(digital_text) >= settings.min_digital_text_chars:
            extractions.append(
                PageExtraction(
                    page_number=page_num,
                    text=digital_text,
                    extraction_method=ExtractionMethod.DIGITAL_PDF.value,
                    char_count=len(digital_text),
                    is_scanned=False,
                    confidence=1.0,
                    ocr_applied=False,
                )
            )
            logger.info(f"Page {page_num}: Extracted {len(digital_text)} digital characters.")
        else:
            # 3. Scanned page candidate: attempt OCR if available
            logger.info(f"Page {page_num}: Digital text deficient ({len(digital_text)} chars). Checking OCR.")
            if ocr.is_available:
                try:
                    preprocessed = preprocess_for_ocr(img)
                    ocr_text, ocr_conf = ocr.extract_text_from_image(preprocessed)
                    extractions.append(
                        PageExtraction(
                            page_number=page_num,
                            text=ocr_text,
                            extraction_method=ExtractionMethod.OCR_TESSERACT.value,
                            char_count=len(ocr_text),
                            is_scanned=True,
                            confidence=ocr_conf,
                            ocr_applied=True,
                        )
                    )
                except Exception as err:
                    extractions.append(
                        PageExtraction(
                            page_number=page_num,
                            text=digital_text,
                            extraction_method=ExtractionMethod.DIGITAL_PDF.value,
                            char_count=len(digital_text),
                            is_scanned=True,
                            confidence=0.3,
                            ocr_applied=False,
                            error=f"OCR fallback failed: {err}",
                        )
                    )
            else:
                extractions.append(
                    PageExtraction(
                        page_number=page_num,
                        text=digital_text,
                        extraction_method=ExtractionMethod.DIGITAL_PDF.value,
                        char_count=len(digital_text),
                        is_scanned=True,
                        confidence=0.5 if digital_text else 0.0,
                        ocr_applied=False,
                        error="Page appears scanned but Tesseract OCR is not installed.",
                    )
                )

    doc.close()
    return extractions, page_images


def extract_from_image(img_path: Path) -> Tuple[List[PageExtraction], List[Image.Image]]:
    """
    Extracts text from standalone image (PNG, JPG, JPEG).
    Requires OCR for non-empty text; gracefully reports status if OCR unavailable.
    """
    try:
        img = Image.open(img_path)
        img.load()
    except Exception as e:
        raise CorruptedFileError(f"Failed to decode image file '{img_path.name}': {str(e)}")

    ocr = get_ocr_engine()
    page_images = [img.copy()]

    if ocr.is_available:
        try:
            preprocessed = preprocess_for_ocr(img)
            ocr_text, conf = ocr.extract_text_from_image(preprocessed)
            return [
                PageExtraction(
                    page_number=1,
                    text=ocr_text,
                    extraction_method=ExtractionMethod.IMAGE_OCR.value,
                    char_count=len(ocr_text),
                    is_scanned=True,
                    confidence=conf,
                    ocr_applied=True,
                )
            ], page_images
        except Exception as e:
            return [
                PageExtraction(
                    page_number=1,
                    text="",
                    extraction_method=ExtractionMethod.IMAGE_OCR.value,
                    char_count=0,
                    is_scanned=True,
                    confidence=0.0,
                    ocr_applied=False,
                    error=f"OCR failed on image: {e}",
                )
            ], page_images

    # OCR not installed
    return [
        PageExtraction(
            page_number=1,
            text="",
            extraction_method=ExtractionMethod.IMAGE_OCR.value,
            char_count=0,
            is_scanned=True,
            confidence=0.0,
            ocr_applied=False,
            error="Image uploaded but Tesseract OCR is not installed. Scanned documents cannot be parsed without OCR.",
        )
    ], page_images
