# Intelligent Document Processing (IDP) System from Scratch

A production-grade, modular Intelligent Document Processing (IDP) application in Python designed to ingest business documents, extract embedded digital text and OCR scans, classify document types, extract structured entities and line items, perform automated accounting validation, and provide an interactive human-in-the-loop review studio with multi-format exports.

Built from scratch with zero proprietary cloud dependencies or mandatory external APIs.

---

## 🌟 Key Features Implemented

- **Robust Ingestion Pipeline:** Validates genuine magic bytes (`%PDF`, `\x89PNG`, `\xff\xd8\xff`), enforces upload file size limits (default 25 MB), prevents path traversal, and uses guaranteed context-manager temporary file deletion.
- **Hybrid Text Extraction:**
  - Fast, direct embedded text extraction on digital PDFs using PyMuPDF (`pymupdf`).
  - Scanned page detection with automated Otsu binarization and contrast preprocessing.
  - Graceful Tesseract OCR fallback with detailed diagnostics when external OCR binaries are not installed.
- **Explainable Document Classification:** Rule and cue scoring engine categorizing documents into **Invoices**, **Receipts**, **Purchase Orders**, **Contracts**, **Business Reports**, or **Unknown** with explicit evidence tracking and human review triggers.
- **Invoice Entity & Line-Item Extraction:** Contextual label-aware regex and proximity parsers extracting Invoice Number, Dates (Issue & Due), Vendor, Customer, Currency, Subtotal, Tax, Discount, Total Amount, Payment Terms, and Purchase Order Number.
- **Differentiator 1: Field Evidence Traceability:** Every extracted field links to its source text snippet, character match, and page number reference for auditability.
- **Differentiator 2: Prioritized Human-in-the-Loop Review:** Automatically prioritizes ambiguous, missing, or mathematically conflicting fields for reviewer attention in the UI before approval.
- **Accounting Validation Engine:** Verifies required fields, checks date sequences (`due_date >= invoice_date`), checks non-negative amounts, audits line item totals, and enforces the fundamental invoice equation:
  $$\text{Subtotal} + \text{Tax} - \text{Discount} = \text{Total Amount} \quad (\pm \text{tolerance})$$
- **Multi-Format Export Engine:** Exports single or batch results into structured **JSON**, **CSV** (with CSV formula injection protection), and multi-sheet **Excel (`.xlsx`)** workbooks.
- **Interactive Streamlit Web Studio:** Clean dashboard featuring single-doc processing, page preview, tabular line items, editable reviewer corrections, batch document processing, and system evaluation metrics.

---

## 🏗 System Architecture

For complete system design diagrams and component breakdowns, see [docs/architecture.md](docs/architecture.md).

```
Document Upload (PDF, PNG, JPG)
       │
       ▼
[Ingestion & Magic Byte Validation]
       │
       ▼
[Hybrid Text Extraction: PyMuPDF + OCR Engine Fallback]
       │
       ▼
[Explainable Document Classification (6 Classes)]
       │
       ▼
[Entity & Tabular Line-Item Extraction with Evidence Traceability]
       │
       ▼
[Data Normalization (ISO 8601 Dates, ISO 4217 Currencies, Floats)]
       │
       ▼
[Accounting Integrity Validation & Audit Checks]
       │
       ▼
[Streamlit Review Studio: Human Verification & Correction]
       │
       ▼
[Secure Multi-Format Exporters (JSON, CSV, Multi-Sheet Excel)]
```

---

## 📁 Project Directory Structure

```
IDPS/
├── app.py                      # Interactive Streamlit Web Interface
├── evaluate.py                 # Ground-truth evaluation & accuracy script
├── requirements.txt            # Production dependencies
├── pyproject.toml              # Build backend and test configuration
├── .gitignore                  # Git exclusion rules
├── .env.example                # Safe environment configuration template
├── README.md                   # Complete system documentation
├── src/
│   └── document_ai/            # Core package
│       ├── __init__.py         # Package exports & version
│       ├── config.py           # Centralized configuration & settings
│       ├── exceptions.py       # Custom exception hierarchy
│       ├── logging_config.py   # Safe structured logger
│       ├── schemas.py          # Data models and serializable schemas
│       ├── ingestion.py        # File validation & safe temp handling
│       ├── pdf_processor.py    # PyMuPDF text & page extraction
│       ├── image_preprocessor.py # Otsu thresholding & contrast enhancement
│       ├── ocr_engine.py       # Tesseract OCR wrapper & fallback
│       ├── document_classifier.py # Rule-based document classifier
│       ├── layout_analyzer.py  # Reading-order line segmentation
│       ├── table_extractor.py  # Line-item table parser
│       ├── field_extractor.py  # Invoice field extraction & evidence
│       ├── normalizer.py       # Date, currency, amount normalizers
│       ├── validator.py        # Accounting consistency validation
│       ├── pipeline.py         # End-to-end pipeline coordinator
│       └── exporters.py        # JSON, CSV, and Excel exports
├── tests/
│   ├── test_ingestion.py       # Ingestion and security tests
│   ├── test_pdf_processor.py   # PDF text extraction tests
│   ├── test_classifier.py      # Classification tests across 6 types
│   ├── test_field_extractor.py # Field & line item extraction tests
│   ├── test_normalizer.py      # Normalization unit tests
│   ├── test_validator.py       # Accounting audit & validation tests
│   ├── test_exporters.py       # JSON, CSV, and Excel export tests
│   └── test_pipeline.py        # Complete end-to-end integration tests
├── fixtures/
│   └── samples/                # Synthetic test documents
│       ├── sample_invoice.pdf  # Synthetic invoice PDF
│       ├── sample_invoice.json # Benchmark ground-truth JSON
│       ├── sample_invoice.png  # Synthetic invoice image
│       ├── sample_receipt.pdf  # Synthetic receipt PDF
│       ├── sample_po.pdf       # Synthetic purchase order PDF
│       ├── sample_contract.pdf # Synthetic contract PDF
│       ├── sample_report.pdf   # Synthetic business report PDF
│       └── sample_corrupt.pdf  # Corrupt PDF for resilience testing
├── scripts/
│   └── generate_samples.py     # Reproducible test fixture generator
└── docs/
    ├── architecture.md         # Architecture documentation & Mermaid diagram
    └── evaluation.md           # Evaluation methodology & metrics
```

---

## 🛠 Technology Stack

- **Python 3.11+** (Tested on Python 3.13)
- **PyMuPDF (`pymupdf`)**: Direct PDF text extraction and page rasterization.
- **Pillow & NumPy**: Image preprocessing, contrast enhancement, and Otsu's binarization.
- **pytesseract**: Interface to Tesseract OCR engine (optional, handled gracefully).
- **pandas & openpyxl**: Structured tabular data aggregation and multi-sheet Excel generation.
- **Streamlit**: Web dashboard for single/batch processing and human review.
- **pytest**: Automated unit and integration testing suite.

---

## 🚀 Installation & Setup

### 1. Clone or Open Project Directory
```powershell
cd C:\Users\Acer\IDPS
```

### 2. Create and Activate Virtual Environment
**Windows PowerShell:**
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

**Linux / macOS:**
```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install Dependencies
```powershell
pip install -r requirements.txt
pip install -e .
```

---

## 🔤 OCR Installation (Optional)

Digital PDFs do not require OCR. For scanned images or flattened PDFs:
- **Windows:** Download the official Tesseract installer from [UB-Mannheim/tesseract](https://github.com/UB-Mannheim/tesseract/wiki).
  - Add `C:\Program Files\Tesseract-OCR` to your system `PATH`, or set `TESSERACT_CMD` in your `.env` file:
    ```ini
    TESSERACT_CMD=C:\Program Files\Tesseract-OCR\tesseract.exe
    ```
- **Linux (Ubuntu/Debian):**
  ```bash
  sudo apt-get update && sudo apt-get install -y tesseract-ocr
  ```
- **macOS:**
  ```bash
  brew install tesseract
  ```

---

## 💻 Running the Application

Launch the Streamlit interactive dashboard:
```powershell
streamlit run app.py
```
Open your browser at `http://localhost:8501`.

---

## 🧪 Running Automated Tests

Run the full pytest suite:
```powershell
pytest
```
Expected output:
```
35 passed in ~2s
```

---

## 📈 Evaluation & Benchmarks

Run the automated evaluation against labeled ground truth:
```powershell
python evaluate.py
```

### Benchmark Results on Synthetic Test Fixtures:
| Metric | Result |
| :--- | :--- |
| **Document Classification Accuracy** | 100% |
| **Field-Level Exact Match Accuracy** | 100% (9/9 fields matched) |
| **Missing Field Rate** | 0.0% |
| **Line Items Parsed** | 3 of 3 items matched |
| **Validation Errors** | 0 |

*See [docs/evaluation.md](docs/evaluation.md) for full evaluation methodology.*

---

## 🚀 Deployment Guide

### Option 1: Streamlit Community Cloud (1-Click Free Public URL)
1. Fork or push changes to [Krishnaprasad0705/Intelligent-Document-Processing-System](https://github.com/Krishnaprasad0705/Intelligent-Document-Processing-System).
2. Log in to [share.streamlit.io](https://share.streamlit.io/).
3. Click **"New App"** and select:
   - **Repository:** `Krishnaprasad0705/Intelligent-Document-Processing-System`
   - **Branch:** `main`
   - **Main file path:** `app.py`
4. Click **"Deploy!"**
   - The included `packages.txt` automatically provisions `tesseract-ocr` and language packs in the Linux cloud runner.

### Option 2: Docker Container Deployment
Run the containerized application with one command:
```bash
docker compose up --build
```
Or with standard Docker:
```bash
docker build -t document-ai-studio .
docker run -p 8501:8501 document-ai-studio
```
Open **http://localhost:8501** in your browser.

---

## 🔒 Security & Privacy Considerations

1. **No External API Leaks:** All extraction, classification, and validation executes locally without cloud API calls or telemetry.
2. **CSV / Excel Formula Injection Sanitization:** Cells starting with dangerous formula characters (`=`, `+`, `-`, `@`) are prepended with `'` to mitigate DDE / formula execution exploits.
3. **Safe File Handling:** Temporary files are stored in isolated scratch directories and guaranteed deleted via context manager cleanup.
4. **Input Size Limits:** Reject oversized files (exceeding 25 MB) and PDFs with excessive pages (> 50 pages) to prevent denial-of-service.

---

## ⚠️ Known Limitations

- **Complex Multi-Column Scans:** Scanned documents without clear reading order require visual bounding-box modeling (e.g. LayoutLM). Current implementation uses rule-based text segmentation.
- **Handwritten Documents:** OCR performance depends on Tesseract engine quality and does not include handwriting recognition models (HTR).
- **International Invoices:** Currency symbols for USD, EUR, GBP, JPY, and INR are supported. Non-standard regional tax systems (e.g., Brazilian Nota Fiscal) require specialized rule extensions.

---

## 📄 Example Structured Output (JSON)

```json
{
  "document_id": "8f3b23e7-142f-4889-913a-96942ad7ff1a",
  "filename": "sample_invoice.pdf",
  "classification": {
    "predicted_type": "invoice",
    "confidence": 0.88,
    "requires_human_review": false
  },
  "extraction_method": "digital_pdf",
  "invoice_data": {
    "invoice_number": "INV-2024-0042",
    "invoice_date": "2024-03-15",
    "due_date": "2024-04-14",
    "vendor_name": "ACME Solutions Inc.",
    "customer_name": "Global Logistics Enterprises",
    "currency": "USD",
    "subtotal": 1700.0,
    "tax_amount": 170.0,
    "discount": 0.0,
    "total_amount": 1870.0,
    "purchase_order_number": "PO-89211",
    "payment_terms": "Net 30"
  },
  "line_items": [
    {
      "description": "Enterprise Cloud Hosting",
      "quantity": 2.0,
      "unit_price": 250.0,
      "line_total": 500.0
    }
  ],
  "validation": {
    "is_valid": true,
    "requires_review": false,
    "error_count": 0,
    "warning_count": 0
  },
  "status": "success"
}
```

---

## 📝 Resume Project Description

**Intelligent Document Processing (IDP) System | Python, PyMuPDF, Tesseract, Streamlit, Pandas, Pytest**
- Engineered an end-to-end Intelligent Document Processing system from scratch with zero proprietary cloud dependencies, extracting structured entities and line items from invoices, receipts, and purchase orders.
- Architected a hybrid extraction engine combining direct PyMuPDF text parsing with an automated Otsu binarization and Tesseract OCR fallback for scanned documents.
- Designed an explainable document classification engine and label-aware entity extractor with full field-level evidence traceability linking values to source page references.
- Implemented an accounting integrity validation engine enforcing mathematical consistency ($\text{Subtotal} + \text{Tax} - \text{Discount} = \text{Total}$) and date sequencing, surfacing prioritized review alerts.
- Built an interactive Streamlit human-in-the-loop review studio with batch processing, CSV formula injection sanitization, and multi-format exports (JSON, CSV, multi-sheet Excel).
- Developed a comprehensive test suite of 37 unit and integration tests with 100% pass rate.
