"""
Tests for PDF processing and direct digital text extraction.
"""

from pathlib import Path
import pytest
import pymupdf
from document_ai.exceptions import CorruptedFileError
from document_ai.pdf_processor import extract_from_image, extract_from_pdf
from document_ai.schemas import ExtractionMethod


def test_extract_digital_pdf(tmp_path: Path):
    pdf_path = tmp_path / "digital.pdf"
    doc = pymupdf.open()
    page = doc.new_page(width=500, height=700)
    page.insert_text((50, 50), "TAX INVOICE INV-1001 Total $500.00", fontsize=12)
    doc.save(str(pdf_path))
    doc.close()

    pages, images = extract_from_pdf(pdf_path)
    assert len(pages) == 1
    assert len(images) == 1
    assert "TAX INVOICE" in pages[0].text
    assert pages[0].extraction_method == ExtractionMethod.DIGITAL_PDF.value
    assert pages[0].char_count > 0
    assert not pages[0].is_scanned


def test_extract_multi_page_pdf(tmp_path: Path):
    pdf_path = tmp_path / "multipage.pdf"
    doc = pymupdf.open()
    for i in range(3):
        p = doc.new_page()
        p.insert_text((50, 50), f"Page {i+1} content with sufficient characters for digital extraction.", fontsize=12)
    doc.save(str(pdf_path))
    doc.close()

    pages, images = extract_from_pdf(pdf_path)
    assert len(pages) == 3
    assert len(images) == 3
    assert pages[0].page_number == 1
    assert pages[1].page_number == 2
    assert pages[2].page_number == 3


def test_extract_corrupt_pdf(tmp_path: Path):
    corrupt_path = tmp_path / "broken.pdf"
    corrupt_path.write_bytes(b"%PDF-1.4 CORRUPTED DATA NOT REAL PDF")
    with pytest.raises(CorruptedFileError):
        extract_from_pdf(corrupt_path)
