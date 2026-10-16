"""
Tests for explainable document classification.
"""

from document_ai.document_classifier import classify_document
from document_ai.schemas import DocumentType, PageExtraction


def test_classify_invoice():
    page = PageExtraction(
        page_number=1,
        text="TAX INVOICE\nInvoice Number: INV-2024-01\nBill To: ACME Corp\nDue Date: 2024-05-01\nSubtotal: $100\nAmount Due: $110",
        extraction_method="digital_pdf",
        char_count=120,
    )
    result = classify_document([page])
    assert result.predicted_type == DocumentType.INVOICE
    assert result.confidence >= 0.7
    assert len(result.evidence) > 0
    assert not result.requires_human_review


def test_classify_receipt():
    page = PageExtraction(
        page_number=1,
        text="CORNER BAKERY\nSTORE #402 POS REGISTER 1\nRECEIPT\nCASHIER: JANE\nCHANGE DUE: $5.00\nTHANK YOU FOR SHOPPING",
        extraction_method="digital_pdf",
        char_count=120,
    )
    result = classify_document([page])
    assert result.predicted_type == DocumentType.RECEIPT
    assert result.confidence >= 0.7


def test_classify_purchase_order():
    page = PageExtraction(
        page_number=1,
        text="PURCHASE ORDER\nPO Number: PO-9912\nVendor Order: ACME Tech\nShip To: Dock 4\nRequisition No: 1204",
        extraction_method="digital_pdf",
        char_count=100,
    )
    result = classify_document([page])
    assert result.predicted_type == DocumentType.PURCHASE_ORDER


def test_classify_contract():
    page = PageExtraction(
        page_number=1,
        text="MASTER SERVICES AGREEMENT\nWHEREAS the parties agree to terms and conditions.\nIN WITNESS WHEREOF, executed under California governing law.",
        extraction_method="digital_pdf",
        char_count=130,
    )
    result = classify_document([page])
    assert result.predicted_type == DocumentType.CONTRACT


def test_classify_business_report():
    page = PageExtraction(
        page_number=1,
        text="ANNUAL REPORT 2024\nTABLE OF CONTENTS\n1. Executive Summary\n2. Key Findings\n3. Methodology\nConclusion and Recommendations",
        extraction_method="digital_pdf",
        char_count=140,
    )
    result = classify_document([page])
    assert result.predicted_type == DocumentType.BUSINESS_REPORT


def test_classify_unknown():
    page = PageExtraction(
        page_number=1,
        text="Hello world, this is a general personal letter about summer holidays and gardening.",
        extraction_method="digital_pdf",
        char_count=85,
    )
    result = classify_document([page])
    assert result.predicted_type == DocumentType.UNKNOWN
    assert result.requires_human_review
