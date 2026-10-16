"""
Export and Serialization Engine.
Exports structured extraction results into JSON, CSV, and multi-sheet Excel workbooks.
Applies CSV injection sanitization (protecting against spreadsheet formula exploits)
and cleanly flattens nested schemas.
"""

from io import BytesIO
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
import pandas as pd

from document_ai.exceptions import ExportError
from document_ai.logging_config import get_logger
from document_ai.schemas import DocumentResult

logger = get_logger("exporters")

# Dangerous prefix characters for CSV/Excel formula injection
DANGEROUS_FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


def sanitize_cell_value(val: Any) -> Any:
    """
    Sanitizes string inputs to prevent CSV/Excel Formula Injection (DDE attacks).
    Prepends a single quote if string starts with dangerous operators.
    """
    if isinstance(val, str):
        if val.startswith(DANGEROUS_FORMULA_PREFIXES):
            return f"'{val}"
    return val


def flatten_document_result(doc: DocumentResult) -> Dict[str, Any]:
    """Flattens a DocumentResult into a single-row dictionary for tabular exports."""
    inv = doc.invoice_data
    val = doc.validation

    row = {
        "document_id": doc.document_id,
        "filename": doc.filename,
        "file_type": doc.metadata.file_type,
        "page_count": doc.metadata.page_count,
        "document_type": doc.classification.predicted_type.value,
        "classification_confidence": doc.classification.confidence,
        "classification_requires_review": doc.classification.requires_human_review,
        "extraction_method": doc.extraction_method,
        "processing_status": doc.status.value,
        "user_reviewed": doc.user_reviewed,
        # Invoice fields
        "invoice_number": inv.invoice_number if inv else None,
        "invoice_date": inv.invoice_date if inv else None,
        "due_date": inv.due_date if inv else None,
        "vendor_name": inv.vendor_name if inv else None,
        "customer_name": inv.customer_name if inv else None,
        "currency": inv.currency if inv else None,
        "subtotal": inv.subtotal if inv else None,
        "tax_amount": inv.tax_amount if inv else None,
        "discount": inv.discount if inv else None,
        "total_amount": inv.total_amount if inv else None,
        "payment_terms": inv.payment_terms if inv else None,
        "purchase_order_number": inv.purchase_order_number if inv else None,
        # Validation stats
        "is_valid": val.is_valid,
        "validation_errors_count": val.error_count,
        "validation_warnings_count": val.warning_count,
        "line_items_count": len(doc.line_items),
        "validation_summary": "; ".join([f"[{m.severity.value}] {m.message}" for m in val.messages]) if val.messages else "Valid",
    }
    # Sanitize each string field
    return {k: sanitize_cell_value(v) for k, v in row.items()}


def flatten_line_items(doc: DocumentResult) -> List[Dict[str, Any]]:
    """Flattens line items linked with document_id and filename."""
    rows = []
    for item in doc.line_items:
        row = {
            "document_id": doc.document_id,
            "filename": doc.filename,
            "page_number": item.page_number,
            "description": sanitize_cell_value(item.description),
            "quantity": item.quantity,
            "unit_price": item.unit_price,
            "tax_rate": item.tax_rate,
            "tax_amount": item.tax_amount,
            "line_total": item.line_total,
            "item_confidence": item.confidence,
        }
        rows.append(row)
    return rows


def export_to_json(
    results: Union[DocumentResult, List[DocumentResult]],
    output_path: Optional[Path] = None,
    indent: int = 2
) -> str:
    """Exports DocumentResult or list of results to formatted JSON string or file."""
    if isinstance(results, DocumentResult):
        data = results.to_dict()
    else:
        data = [r.to_dict() for r in results]

    json_str = json.dumps(data, indent=indent, default=str)

    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(json_str)

    return json_str


def export_to_csv(
    results: Union[DocumentResult, List[DocumentResult]],
    output_path: Optional[Path] = None,
    include_line_items: bool = False,
) -> str:
    """
    Exports summary rows to CSV format.
    If include_line_items is True and single doc, exports line items table instead.
    """
    docs = [results] if isinstance(results, DocumentResult) else results

    if include_line_items:
        rows = []
        for d in docs:
            rows.extend(flatten_line_items(d))
        df = pd.DataFrame(rows)
    else:
        rows = [flatten_document_result(d) for d in docs]
        df = pd.DataFrame(rows)

    csv_data = df.to_csv(index=False)

    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8", newline="") as f:
            f.write(csv_data)

    return csv_data


def export_to_excel(
    results: Union[DocumentResult, List[DocumentResult]],
    output_path: Optional[Path] = None,
) -> bytes:
    """
    Exports results to a multi-sheet Excel workbook:
    - Sheet 1: 'Invoices_Summary'
    - Sheet 2: 'Line_Items'
    """
    docs = [results] if isinstance(results, DocumentResult) else results

    summary_rows = [flatten_document_result(d) for d in docs]
    line_rows: List[Dict[str, Any]] = []
    for d in docs:
        line_rows.extend(flatten_line_items(d))

    df_summary = pd.DataFrame(summary_rows)
    df_lines = pd.DataFrame(line_rows) if line_rows else pd.DataFrame([{"message": "No line items found"}])

    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df_summary.to_excel(writer, sheet_name="Invoices_Summary", index=False)
        df_lines.to_excel(writer, sheet_name="Line_Items", index=False)

    excel_bytes = buffer.getvalue()

    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "wb") as f:
            f.write(excel_bytes)

    return excel_bytes
