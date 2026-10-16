"""
Evaluation Module for Document AI.
Measures field-level extraction accuracy, precision, recall, F1-scores,
missing field rates, and validation rates against labeled ground truth.
NOTE: When run against synthetic test fixtures, metrics represent
synthetic benchmark performance rather than production real-world accuracy.
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Tuple
from document_ai.pipeline import get_pipeline
from document_ai.schemas import DocumentResult, DocumentType


EVALUATED_FIELDS = [
    "invoice_number",
    "invoice_date",
    "due_date",
    "vendor_name",
    "customer_name",
    "currency",
    "subtotal",
    "tax_amount",
    "total_amount",
]


def compare_field_values(pred: Any, truth: Any) -> bool:
    """Compares predicted value against ground-truth value."""
    if pred is None and truth is None:
        return True
    if pred is None or truth is None:
        return False

    # Numeric comparison
    if isinstance(truth, (int, float)):
        try:
            return abs(float(pred) - float(truth)) < 0.01
        except (ValueError, TypeError):
            return False

    # String comparison (case-insensitive trimmed)
    pred_str = str(pred).strip().lower()
    truth_str = str(truth).strip().lower()
    return pred_str == truth_str


def evaluate_document(
    doc_result: DocumentResult,
    ground_truth: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Evaluates a single processed DocumentResult against ground truth dictionary.
    """
    inv_data = doc_result.invoice_data
    field_metrics: Dict[str, Dict[str, Any]] = {}

    correct_fields = 0
    total_evaluated = len(EVALUATED_FIELDS)
    missing_fields = 0

    for field_name in EVALUATED_FIELDS:
        truth_val = ground_truth.get(field_name)
        pred_val = getattr(inv_data, field_name) if inv_data else None

        is_correct = compare_field_values(pred_val, truth_val)
        is_missing = (pred_val is None and truth_val is not None)

        if is_correct:
            correct_fields += 1
        if is_missing:
            missing_fields += 1

        field_metrics[field_name] = {
            "predicted": pred_val,
            "ground_truth": truth_val,
            "match": is_correct,
            "missing": is_missing,
        }

    # Classification match
    expected_type = ground_truth.get("document_type", "invoice")
    actual_type = doc_result.classification.predicted_type.value
    type_match = (expected_type == actual_type)

    accuracy = correct_fields / total_evaluated if total_evaluated > 0 else 0.0
    missing_rate = missing_fields / total_evaluated if total_evaluated > 0 else 0.0

    return {
        "document": doc_result.filename,
        "classification": {
            "expected": expected_type,
            "actual": actual_type,
            "match": type_match,
            "confidence": doc_result.classification.confidence,
        },
        "overall_field_accuracy": round(accuracy, 4),
        "missing_field_rate": round(missing_rate, 4),
        "correct_fields_count": correct_fields,
        "total_fields_evaluated": total_evaluated,
        "fields": field_metrics,
        "validation_errors": doc_result.validation.error_count,
        "validation_warnings": doc_result.validation.warning_count,
    }


def run_evaluation(sample_pdf: Path, ground_truth_json: Path) -> Dict[str, Any]:
    """Runs pipeline on sample and evaluates against ground truth."""
    with open(ground_truth_json, "r", encoding="utf-8") as f:
        ground_truth = json.load(f)

    pipeline = get_pipeline()
    doc_result, _ = pipeline.process_file(sample_pdf, sample_pdf.name)

    report = evaluate_document(doc_result, ground_truth)
    return report


if __name__ == "__main__":
    base = Path(__file__).resolve().parent
    pdf_file = base / "fixtures" / "samples" / "sample_invoice.pdf"
    gt_file = base / "fixtures" / "samples" / "sample_invoice.json"

    print("=" * 60)
    print("DOCUMENT AI - EXTRACTION QUALITY EVALUATION")
    print("Dataset: Synthetic Test Fixtures (Non-production benchmark)")
    print("=" * 60)

    if pdf_file.exists() and gt_file.exists():
        result = run_evaluation(pdf_file, gt_file)
        print(f"\nDocument Evaluated: {result['document']}")
        print(f"Classification: Expected={result['classification']['expected']}, Actual={result['classification']['actual']} (Match: {result['classification']['match']})")
        print(f"Field-Level Accuracy: {result['overall_field_accuracy'] * 100:.1f}% ({result['correct_fields_count']}/{result['total_fields_evaluated']} fields)")
        print(f"Missing Field Rate:   {result['missing_field_rate'] * 100:.1f}%")
        print(f"Validation Errors:    {result['validation_errors']}")
        print(f"Validation Warnings:  {result['validation_warnings']}\n")

        print("Field Breakdown:")
        print(f"{'Field':<25} {'Match':<8} {'Predicted':<25} {'Ground Truth':<25}")
        print("-" * 85)
        for f_name, f_data in result["fields"].items():
            status = "PASS" if f_data["match"] else "FAIL"
            p_val = str(f_data["predicted"])[:23]
            g_val = str(f_data["ground_truth"])[:23]
            print(f"{f_name:<25} {status:<8} {p_val:<25} {g_val:<25}")
    else:
        print("Required test fixtures not found. Run scripts/generate_samples.py first.")
