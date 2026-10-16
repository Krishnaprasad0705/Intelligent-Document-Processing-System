# Document AI - Evaluation Methodology & Metrics

This document details the evaluation framework, measurement metrics, benchmarking procedure, and known boundaries of the Intelligent Document Processing (IDP) system.

---

## 1. Evaluation Methodology

Automated evaluation compares extracted document information against manually curated ground-truth annotations stored in JSON schema format (e.g., [`sample_invoice.json`](file:///c:/Users/Acer/IDPS/fixtures/samples/sample_invoice.json)).

### Evaluation Pipeline
1. Ingest input document (PDF or image).
2. Run text extraction, classification, field extraction, and table parsing.
3. Compare extracted fields against labeled ground truth.
4. Calculate field-level exact match, precision, recall, missing field rate, and validation health.

---

## 2. Core Metrics

### Field-Level Exact Match Accuracy
Measures whether an extracted field matches the expected ground-truth value:
$$\text{Accuracy} = \frac{\sum_{i=1}^{N} \mathbb{I}(\text{pred}_i == \text{truth}_i)}{N}$$

- **Numeric Fields (Monetary & Quantities):** Evaluated with floating-point tolerance of $| \text{pred} - \text{truth} | < 0.01$.
- **Date Fields:** Normalized into ISO 8601 (`YYYY-MM-DD`) before comparison to avoid penalizing format differences (e.g. `15-Mar-2024` vs `2024-03-15`).
- **Text Fields:** Case-insensitive string matching after trimming and space collapsing.

### Missing Field Rate
$$\text{Missing Rate} = \frac{\text{Count of fields present in ground truth but None in predictions}}{\text{Total fields in ground truth}}$$

A high missing rate indicates weak label detection or overly restrictive regular expressions.

### Validation Error and Warning Rate
Measures how many business logic errors (e.g. arithmetic inconsistencies, negative amounts, inverted dates) are caught by the validation layer.

---

## 3. Evaluated Fields

| Field Name | Type | Description |
| :--- | :--- | :--- |
| `invoice_number` | String | Unique invoice reference identifier |
| `invoice_date` | Date (ISO) | Date of invoice issuance |
| `due_date` | Date (ISO) | Payment due date |
| `vendor_name` | String | Issuer or supplier organization |
| `customer_name` | String | Buyer or billed entity |
| `currency` | String | 3-letter ISO-4217 code (e.g., `USD`, `EUR`) |
| `subtotal` | Float | Net amount before taxes and discounts |
| `tax_amount` | Float | Total calculated tax / VAT |
| `total_amount` | Float | Final payable amount |
| `line_items` | Array | Parsed items (Description, Qty, Unit Price, Line Total) |

---

## 4. Benchmark Performance on Included Synthetic Fixtures

> [!NOTE]
> **Synthetic Test Performance Disclaimer**
> The benchmark metrics below were calculated on synthetic test fixtures included in the repository. They demonstrate that the parsing rules, regular expressions, normalization logic, and validation formulas operate accurately on conforming document layouts. Real-world document accuracy will vary depending on scan resolution, OCR quality, multi-column variations, and non-standard layouts.

### Synthetic Benchmark Results (`sample_invoice.pdf`)
- **Document Classification Accuracy:** 100% (`invoice` correctly identified with high confidence)
- **Field-Level Exact Match Accuracy:** 100% (9/9 fields matched)
- **Missing Field Rate:** 0.0%
- **Line Items Extracted:** 3 of 3 items matched accurately
- **Validation Errors:** 0
- **Validation Warnings:** 0

---

## 5. Running the Evaluation Script

To run the automated evaluation on the current workspace fixtures:

```powershell
# Windows PowerShell
.\.venv\Scripts\python evaluate.py

# Linux / macOS
python3 evaluate.py
```
