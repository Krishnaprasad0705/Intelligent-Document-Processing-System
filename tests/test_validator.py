"""
Tests for validation engine, accounting equations, and warning alerts.
"""

from document_ai.schemas import InvoiceFields, LineItem, ValidationSeverity
from document_ai.validator import validate_invoice


def test_validation_clean_invoice():
    inv = InvoiceFields(
        invoice_number="INV-001",
        invoice_date="2024-01-01",
        due_date="2024-01-31",
        vendor_name="Tech Corp",
        customer_name="Client LLC",
        currency="USD",
        subtotal=100.00,
        tax_amount=10.00,
        discount=0.00,
        total_amount=110.00,
    )
    items = [
        LineItem(description="Item 1", quantity=2, unit_price=50, line_total=100.00)
    ]
    res = validate_invoice(inv, items)
    assert res.is_valid
    assert not res.requires_review
    assert res.error_count == 0


def test_validation_arithmetic_mismatch():
    inv = InvoiceFields(
        invoice_number="INV-001",
        invoice_date="2024-01-01",
        subtotal=100.00,
        tax_amount=10.00,
        discount=0.00,
        total_amount=125.00,  # Expected 110.00, mismatch!
    )
    res = validate_invoice(inv, [])
    assert not res.is_valid
    assert res.error_count >= 1
    assert any(m.code == "ERR_ARITHMETIC_MISMATCH" for m in res.messages)


def test_validation_missing_mandatory_fields():
    inv = InvoiceFields(
        invoice_number=None,  # Missing!
        invoice_date=None,    # Missing!
        total_amount=None,    # Missing!
    )
    res = validate_invoice(inv, [])
    assert not res.is_valid
    assert res.error_count >= 3


def test_validation_date_order_inverted():
    inv = InvoiceFields(
        invoice_number="INV-002",
        invoice_date="2024-05-15",
        due_date="2024-05-01",  # Due date is before invoice date!
        total_amount=100.00,
    )
    res = validate_invoice(inv, [])
    assert any(m.code == "WARN_DATE_ORDER" for m in res.messages)


def test_validation_line_item_sum_mismatch():
    inv = InvoiceFields(
        invoice_number="INV-003",
        invoice_date="2024-01-01",
        subtotal=200.00,
        total_amount=200.00,
    )
    items = [
        LineItem(description="Item A", line_total=50.00),
        LineItem(description="Item B", line_total=50.00),
        # Sum is 100.00, but subtotal is 200.00!
    ]
    res = validate_invoice(inv, items)
    assert any(m.code == "WARN_LINE_ITEMS_SUM_MISMATCH" for m in res.messages)
