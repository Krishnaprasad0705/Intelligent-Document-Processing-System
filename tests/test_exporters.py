"""
Tests for structured serialization and export (JSON, CSV, Excel)
with formula injection protection.
"""

from io import BytesIO
import json
from pathlib import Path
import pandas as pd
from document_ai.exporters import (
    export_to_csv,
    export_to_excel,
    export_to_json,
    sanitize_cell_value,
)
from document_ai.schemas import (
    DocumentClassification,
    DocumentMetadata,
    DocumentResult,
    DocumentType,
    InvoiceFields,
    LineItem,
    ProcessingStatus,
    ValidationResult,
)


def create_dummy_doc_result() -> DocumentResult:
    return DocumentResult(
        document_id="doc-1234",
        filename="test_inv.pdf",
        metadata=DocumentMetadata(
            filename="test_inv.pdf",
            file_type="pdf",
            file_size_bytes=1024,
            page_count=1,
            created_at="2024-01-01T00:00:00Z",
            checksum_sha256="abc123hash",
        ),
        classification=DocumentClassification(
            predicted_type=DocumentType.INVOICE,
            confidence=0.95,
        ),
        extraction_method="digital_pdf",
        invoice_data=InvoiceFields(
            invoice_number="INV-99",
            invoice_date="2024-01-15",
            vendor_name="Acme Corp",
            customer_name="Client Co",
            currency="USD",
            subtotal=100.0,
            tax_amount=10.0,
            total_amount=110.0,
        ),
        line_items=[
            LineItem(description="Widget A", quantity=2, unit_price=50, line_total=100)
        ],
        validation=ValidationResult(is_valid=True),
        status=ProcessingStatus.SUCCESS,
    )


def test_sanitize_formula_injection():
    # Excel/CSV formula injection attacks start with =, +, -, @
    assert sanitize_cell_value("=1+1") == "'=1+1"
    assert sanitize_cell_value("+cmd|' /C calc'!A0") == "'+cmd|' /C calc'!A0"
    assert sanitize_cell_value("-50.00") == "'-50.00"
    assert sanitize_cell_value("@SUM(A1:A10)") == "'@SUM(A1:A10)"
    assert sanitize_cell_value("Normal text") == "Normal text"


def test_export_to_json(tmp_path: Path):
    doc = create_dummy_doc_result()
    out_file = tmp_path / "out.json"

    json_str = export_to_json(doc, output_path=out_file)
    assert out_file.exists()

    # Read back and verify structure
    with open(out_file, "r", encoding="utf-8") as f:
        loaded = json.load(f)

    assert loaded["document_id"] == "doc-1234"
    assert loaded["invoice_data"]["invoice_number"] == "INV-99"
    assert loaded["invoice_data"]["total_amount"] == 110.0
    assert len(loaded["line_items"]) == 1


def test_export_to_csv(tmp_path: Path):
    doc = create_dummy_doc_result()
    out_file = tmp_path / "out.csv"

    csv_str = export_to_csv([doc], output_path=out_file)
    assert out_file.exists()

    df = pd.read_csv(out_file)
    assert len(df) == 1
    assert df["invoice_number"].iloc[0] == "INV-99"
    assert float(df["total_amount"].iloc[0]) == 110.0


def test_export_to_excel(tmp_path: Path):
    doc = create_dummy_doc_result()
    out_file = tmp_path / "out.xlsx"

    excel_bytes = export_to_excel([doc], output_path=out_file)
    assert out_file.exists()
    assert len(excel_bytes) > 0

    # Read back both sheets using pandas
    xls = pd.ExcelFile(out_file)
    assert "Invoices_Summary" in xls.sheet_names
    assert "Line_Items" in xls.sheet_names

    df_sum = pd.read_excel(xls, "Invoices_Summary")
    df_items = pd.read_excel(xls, "Line_Items")

    assert len(df_sum) == 1
    assert df_sum["invoice_number"].iloc[0] == "INV-99"
    assert len(df_items) == 1
    assert df_items["description"].iloc[0] == "Widget A"
