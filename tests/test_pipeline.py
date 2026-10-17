"""
Integration tests for the complete Document AI processing pipeline.
"""

from pathlib import Path
import pytest
from document_ai.pipeline import get_pipeline
from document_ai.schemas import DocumentType, ProcessingStatus


@pytest.fixture
def sample_dir() -> Path:
    return Path(__file__).resolve().parent.parent / "fixtures" / "samples"


def test_pipeline_end_to_end_invoice(sample_dir: Path):
    inv_pdf = sample_dir / "sample_invoice.pdf"
    assert inv_pdf.exists(), "Sample invoice PDF must exist"

    pipeline = get_pipeline()
    result, images = pipeline.process_file(inv_pdf, inv_pdf.name)

    assert result.status == ProcessingStatus.SUCCESS
    assert result.classification.predicted_type == DocumentType.INVOICE
    assert result.classification.confidence > 0.8
    assert result.invoice_data is not None
    assert result.invoice_data.invoice_number == "INV-2024-0042"
    assert result.invoice_data.total_amount == 1870.0
    assert result.invoice_data.subtotal == 1700.0
    assert result.invoice_data.tax_amount == 170.0
    assert len(result.line_items) == 3
    assert result.validation.is_valid
    assert len(images) >= 1


def test_pipeline_end_to_end_contract(sample_dir: Path):
    contract_pdf = sample_dir / "sample_contract.pdf"
    assert contract_pdf.exists()

    pipeline = get_pipeline()
    result, _ = pipeline.process_file(contract_pdf, contract_pdf.name)

    assert result.classification.predicted_type == DocumentType.CONTRACT
    # Contract should not trigger invoice field extraction unless forced
    assert result.invoice_data is None


def test_pipeline_batch_processing_resilience(sample_dir: Path):
    valid_pdf = sample_dir / "sample_invoice.pdf"
    corrupt_pdf = sample_dir / "sample_corrupt.pdf"

    batch = [
        (valid_pdf, valid_pdf.name),
        (corrupt_pdf, corrupt_pdf.name),
    ]

    pipeline = get_pipeline()
    results = pipeline.process_batch(batch)

    assert len(results) == 2
    # First file succeeds
    assert results[0].filename == valid_pdf.name
    assert results[0].status == ProcessingStatus.SUCCESS

    # Second file fails gracefully without crashing batch
    assert results[1].filename == corrupt_pdf.name
    assert results[1].status == ProcessingStatus.FAILED
    assert len(results[1].errors) > 0


def test_pipeline_human_review_override(sample_dir: Path):
    inv_pdf = sample_dir / "sample_invoice.pdf"
    pipeline = get_pipeline()
    result, _ = pipeline.process_file(inv_pdf, inv_pdf.name)

    assert not result.user_reviewed
    # Simulate user correction in review interface
    result.user_overrides["invoice_number"] = "INV-2024-CORRECTED"
    result.user_reviewed = True

    data = result.to_dict()
    assert data["user_reviewed"] is True
    assert data["user_overrides"]["invoice_number"] == "INV-2024-CORRECTED"


def test_pipeline_image_ocr_zylker(sample_dir: Path):
    zylker_img = sample_dir / "zylker_invoice.png"
    if not zylker_img.exists():
        pytest.skip("Zylker sample image not found")

    pipeline = get_pipeline()
    result, images = pipeline.process_file(zylker_img, zylker_img.name)

    assert result.status == ProcessingStatus.SUCCESS
    assert result.classification.predicted_type == DocumentType.INVOICE
    assert result.invoice_data is not None
    assert result.invoice_data.invoice_number == "INV-000001"
    assert result.invoice_data.invoice_date == "2024-08-05"
    assert result.invoice_data.vendor_name == "Zylker Electronics Hub"
    assert result.invoice_data.customer_name == "Ms. Mary D. Dunton"
    assert result.invoice_data.subtotal == 2227.0
    assert result.invoice_data.total_amount == 2338.35
    assert len(result.line_items) >= 2


def test_pipeline_image_ocr_graphic(sample_dir: Path):
    graphic_img = sample_dir / "graphic_design_invoice.png"
    if not graphic_img.exists():
        pytest.skip("Graphic design sample image not found")

    pipeline = get_pipeline()
    result, images = pipeline.process_file(graphic_img, graphic_img.name)

    assert result.classification.predicted_type == DocumentType.INVOICE
    assert result.invoice_data is not None
    assert result.invoice_data.invoice_date == "2025-06-01"
    assert result.invoice_data.due_date == "2025-06-14"
    assert result.invoice_data.total_amount == 1650.0

