"""
Tests for invoice field extraction and line item parsing.
"""

from document_ai.field_extractor import extract_invoice_fields
from document_ai.schemas import PageExtraction
from document_ai.table_extractor import extract_table_items


def test_extract_invoice_fields():
    invoice_text = (
        "ACME Technologies Inc.\n"
        "TAX INVOICE\n\n"
        "Invoice Number: INV-2024-9988\n"
        "Invoice Date: 2024-06-01\n"
        "Due Date: 2024-06-30\n"
        "Purchase Order Number: PO-1029\n"
        "Payment Terms: Net 30\n\n"
        "BILL TO:\n"
        "Apex Global Logistics\n"
        "100 Main Street, Suite 500\n\n"
        "Subtotal: $2,000.00\n"
        "Tax Amount: $200.00\n"
        "Discount: $50.00\n"
        "Total Amount: $2,150.00\n"
    )

    page = PageExtraction(
        page_number=1,
        text=invoice_text,
        extraction_method="digital_pdf",
        char_count=len(invoice_text),
    )

    inv = extract_invoice_fields([page])

    assert inv.invoice_number == "INV-2024-9988"
    assert inv.invoice_date == "2024-06-01"
    assert inv.due_date == "2024-06-30"
    assert inv.purchase_order_number == "PO-1029"
    assert inv.payment_terms == "Net 30"
    assert inv.vendor_name == "ACME Technologies Inc."
    assert "Apex Global Logistics" in (inv.customer_name or "")
    assert inv.currency == "USD"
    assert inv.subtotal == 2000.00
    assert inv.tax_amount == 200.00
    assert inv.discount == 50.00
    assert inv.total_amount == 2150.00

    # Evidence checks
    assert "invoice_number" in inv.field_evidence
    assert inv.field_evidence["invoice_number"].page_number == 1
    assert "total_amount" in inv.field_evidence


def test_extract_table_items():
    table_text = (
        "TAX INVOICE\n"
        "Invoice No: INV-100\n\n"
        "Description                       Qty      Unit Price        Line Total\n"
        "-----------------------------------------------------------------------\n"
        "Cloud Hosting Services              2          150.00            300.00\n"
        "API Security Audit                  1          500.00            500.00\n"
        "-----------------------------------------------------------------------\n"
        "Subtotal: $800.00\n"
        "Total: $800.00\n"
    )

    page = PageExtraction(
        page_number=1,
        text=table_text,
        extraction_method="digital_pdf",
        char_count=len(table_text),
    )

    items = extract_table_items([page])
    assert len(items) == 2
    assert items[0].description == "Cloud Hosting Services"
    assert items[0].quantity == 2.0
    assert items[0].unit_price == 150.0
    assert items[0].line_total == 300.0

    assert items[1].description == "API Security Audit"
    assert items[1].quantity == 1.0
    assert items[1].unit_price == 500.0
    assert items[1].line_total == 500.0
