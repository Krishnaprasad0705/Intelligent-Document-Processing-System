"""
Validation and Accounting Consistency Engine.
Verifies business logic, required fields, date sequencing, non-negative amounts,
and accounting equations (subtotal + tax - discount == total).
Distinguishes errors, warnings, missing values, and human review requirements.
"""

from datetime import datetime
from typing import List, Optional
from document_ai.config import get_settings
from document_ai.logging_config import get_logger
from document_ai.schemas import (
    InvoiceFields,
    LineItem,
    ValidationMessage,
    ValidationResult,
    ValidationSeverity,
)

logger = get_logger("validator")


class InvoiceValidator:
    """Performs deterministic validation checks on extracted invoice data."""

    def __init__(self, rounding_tolerance: Optional[float] = None) -> None:
        settings = get_settings()
        self.tolerance = rounding_tolerance if rounding_tolerance is not None else settings.rounding_tolerance

    def validate(
        self,
        invoice: Optional[InvoiceFields],
        line_items: List[LineItem]
    ) -> ValidationResult:
        messages: List[ValidationMessage] = []

        if invoice is None:
            messages.append(
                ValidationMessage(
                    severity=ValidationSeverity.ERROR,
                    code="MISSING_INVOICE_DATA",
                    field=None,
                    message="No invoice fields were identified for validation.",
                )
            )
            return ValidationResult(is_valid=False, requires_review=True, messages=messages)

        # 1. Check required fields
        if not invoice.invoice_number:
            messages.append(
                ValidationMessage(
                    severity=ValidationSeverity.ERROR,
                    code="REQ_INVOICE_NUMBER_MISSING",
                    field="invoice_number",
                    message="Missing required field: Invoice Number.",
                )
            )

        if not invoice.invoice_date:
            messages.append(
                ValidationMessage(
                    severity=ValidationSeverity.ERROR,
                    code="REQ_INVOICE_DATE_MISSING",
                    field="invoice_date",
                    message="Missing required field: Invoice Date.",
                )
            )

        if invoice.total_amount is None:
            messages.append(
                ValidationMessage(
                    severity=ValidationSeverity.ERROR,
                    code="REQ_TOTAL_AMOUNT_MISSING",
                    field="total_amount",
                    message="Missing required field: Total Amount.",
                )
            )

        if not invoice.vendor_name:
            messages.append(
                ValidationMessage(
                    severity=ValidationSeverity.WARNING,
                    code="WARN_VENDOR_MISSING",
                    field="vendor_name",
                    message="Vendor/Supplier name could not be identified with confidence.",
                )
            )

        # 2. Date consistency (Due Date >= Invoice Date)
        if invoice.invoice_date and invoice.due_date:
            try:
                inv_dt = datetime.strptime(invoice.invoice_date, "%Y-%m-%d")
                due_dt = datetime.strptime(invoice.due_date, "%Y-%m-%d")
                if due_dt < inv_dt:
                    messages.append(
                        ValidationMessage(
                            severity=ValidationSeverity.WARNING,
                            code="WARN_DATE_ORDER",
                            field="due_date",
                            message="Due date is earlier than the invoice issuance date.",
                            expected=f">= {invoice.invoice_date}",
                            actual=invoice.due_date,
                        )
                    )
            except ValueError:
                pass

        # 3. Non-negative amount checks
        if invoice.total_amount is not None and invoice.total_amount < 0:
            messages.append(
                ValidationMessage(
                    severity=ValidationSeverity.WARNING,
                    code="WARN_NEGATIVE_TOTAL",
                    field="total_amount",
                    message="Total amount is negative. Verify if this is a Credit Note / Refund.",
                    actual=str(invoice.total_amount),
                )
            )

        if invoice.subtotal is not None and invoice.subtotal < 0:
            messages.append(
                ValidationMessage(
                    severity=ValidationSeverity.WARNING,
                    code="WARN_NEGATIVE_SUBTOTAL",
                    field="subtotal",
                    message="Subtotal amount is negative.",
                    actual=str(invoice.subtotal),
                )
            )

        # 4. Accounting equation check: Subtotal + Tax - Discount == Total
        if (
            invoice.subtotal is not None
            and invoice.tax_amount is not None
            and invoice.total_amount is not None
        ):
            discount = invoice.discount or 0.0
            expected_total = round(invoice.subtotal + invoice.tax_amount - discount, 2)
            delta = abs(expected_total - invoice.total_amount)

            if delta > self.tolerance:
                messages.append(
                    ValidationMessage(
                        severity=ValidationSeverity.ERROR,
                        code="ERR_ARITHMETIC_MISMATCH",
                        field="total_amount",
                        message=(
                            f"Arithmetic mismatch: Subtotal ({invoice.subtotal}) + "
                            f"Tax ({invoice.tax_amount}) - Discount ({discount}) = {expected_total}, "
                            f"but Total Amount is {invoice.total_amount} (diff: {delta:.2f})."
                        ),
                        expected=f"{expected_total:.2f}",
                        actual=f"{invoice.total_amount:.2f}",
                    )
                )

        # 5. Line item aggregation check
        if line_items:
            valid_totals = [item.line_total for item in line_items if item.line_total is not None]
            if len(valid_totals) == len(line_items):
                line_sum = round(sum(valid_totals), 2)
                # Compare against subtotal if present, otherwise total
                target_amount = invoice.subtotal if invoice.subtotal is not None else invoice.total_amount
                target_name = "subtotal" if invoice.subtotal is not None else "total_amount"

                if target_amount is not None:
                    delta = abs(line_sum - target_amount)
                    if delta > self.tolerance:
                        messages.append(
                            ValidationMessage(
                                severity=ValidationSeverity.WARNING,
                                code="WARN_LINE_ITEMS_SUM_MISMATCH",
                                field=target_name,
                                message=(
                                    f"Sum of {len(line_items)} line items ({line_sum:.2f}) does not match "
                                    f"invoice {target_name} ({target_amount:.2f})."
                                ),
                                expected=f"{target_amount:.2f}",
                                actual=f"{line_sum:.2f}",
                            )
                        )

        # 6. Currency presence check
        if not invoice.currency:
            messages.append(
                ValidationMessage(
                    severity=ValidationSeverity.WARNING,
                    code="WARN_CURRENCY_MISSING",
                    field="currency",
                    message="Currency code was not detected.",
                )
            )

        # Determine overall validity and review necessity
        has_errors = any(m.severity == ValidationSeverity.ERROR for m in messages)
        has_warnings = any(m.severity == ValidationSeverity.WARNING for m in messages)
        requires_review = has_errors or has_warnings

        return ValidationResult(
            is_valid=not has_errors,
            requires_review=requires_review,
            messages=messages,
        )


_VALIDATOR = InvoiceValidator()


def validate_invoice(
    invoice: Optional[InvoiceFields],
    line_items: List[LineItem],
    tolerance: Optional[float] = None
) -> ValidationResult:
    """Convenience validation entry point."""
    if tolerance is not None:
        validator = InvoiceValidator(rounding_tolerance=tolerance)
        return validator.validate(invoice, line_items)
    return _VALIDATOR.validate(invoice, line_items)
