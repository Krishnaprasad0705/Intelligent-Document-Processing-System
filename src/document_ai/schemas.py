"""
Document AI Data Schemas.
Pure-Python dataclasses defining all data structures throughout the pipeline:
ingestion metadata, page extractions, classification results, field evidence,
line items, validation flags, and final structured output.
"""

from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Dict, List, Optional
import json


class DocumentType(str, Enum):
    INVOICE = "invoice"
    RECEIPT = "receipt"
    PURCHASE_ORDER = "purchase_order"
    CONTRACT = "contract"
    BUSINESS_REPORT = "business_report"
    UNKNOWN = "unknown"


class ExtractionMethod(str, Enum):
    DIGITAL_PDF = "digital_pdf"
    OCR_TESSERACT = "ocr_tesseract"
    IMAGE_OCR = "image_ocr"
    HYBRID = "hybrid"
    UNPROCESSED = "unprocessed"


class ProcessingStatus(str, Enum):
    SUCCESS = "success"
    WARNINGS = "warnings"
    FAILED = "failed"
    REVIEW_REQUIRED = "review_required"


class ValidationSeverity(str, Enum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


@dataclass
class DocumentMetadata:
    filename: str
    file_type: str
    file_size_bytes: int
    page_count: int
    created_at: str
    checksum_sha256: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class PageExtraction:
    page_number: int
    text: str
    extraction_method: str
    char_count: int
    is_scanned: bool = False
    confidence: float = 1.0
    ocr_applied: bool = False
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ClassificationEvidence:
    cue: str
    weight: float
    matched_text: str
    page_number: int

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class DocumentClassification:
    predicted_type: DocumentType
    confidence: float
    evidence: List[ClassificationEvidence] = field(default_factory=list)
    requires_human_review: bool = False
    score_breakdown: Dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        res = asdict(self)
        res["predicted_type"] = self.predicted_type.value
        return res


@dataclass
class FieldEvidence:
    field_name: str
    raw_value: Optional[str]
    matched_text: str
    page_number: int
    confidence: float
    context_snippet: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class LineItem:
    description: str
    quantity: Optional[float] = None
    unit_price: Optional[float] = None
    tax_rate: Optional[float] = None
    tax_amount: Optional[float] = None
    line_total: Optional[float] = None
    page_number: int = 1
    raw_text: str = ""
    confidence: float = 1.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ValidationMessage:
    severity: ValidationSeverity
    code: str
    field: Optional[str]
    message: str
    expected: Optional[str] = None
    actual: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        res = asdict(self)
        res["severity"] = self.severity.value
        return res


@dataclass
class ValidationResult:
    is_valid: bool = True
    requires_review: bool = False
    messages: List[ValidationMessage] = field(default_factory=list)

    @property
    def error_count(self) -> int:
        return sum(1 for m in self.messages if m.severity == ValidationSeverity.ERROR)

    @property
    def warning_count(self) -> int:
        return sum(1 for m in self.messages if m.severity == ValidationSeverity.WARNING)

    @property
    def review_fields(self) -> List[str]:
        return [m.field for m in self.messages if m.field and m.severity in (ValidationSeverity.ERROR, ValidationSeverity.WARNING)]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "is_valid": self.is_valid,
            "requires_review": self.requires_review,
            "error_count": self.error_count,
            "warning_count": self.warning_count,
            "messages": [m.to_dict() for m in self.messages],
            "review_fields": self.review_fields
        }


@dataclass
class InvoiceFields:
    invoice_number: Optional[str] = None
    invoice_date: Optional[str] = None
    due_date: Optional[str] = None
    vendor_name: Optional[str] = None
    customer_name: Optional[str] = None
    currency: Optional[str] = None
    subtotal: Optional[float] = None
    tax_amount: Optional[float] = None
    discount: Optional[float] = None
    total_amount: Optional[float] = None
    payment_terms: Optional[str] = None
    purchase_order_number: Optional[str] = None
    field_evidence: Dict[str, FieldEvidence] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        res = {
            "invoice_number": self.invoice_number,
            "invoice_date": self.invoice_date,
            "due_date": self.due_date,
            "vendor_name": self.vendor_name,
            "customer_name": self.customer_name,
            "currency": self.currency,
            "subtotal": self.subtotal,
            "tax_amount": self.tax_amount,
            "discount": self.discount,
            "total_amount": self.total_amount,
            "payment_terms": self.payment_terms,
            "purchase_order_number": self.purchase_order_number,
            "field_evidence": {k: v.to_dict() for k, v in self.field_evidence.items()}
        }
        return res


@dataclass
class DocumentResult:
    document_id: str
    filename: str
    metadata: DocumentMetadata
    classification: DocumentClassification
    extraction_method: str
    pages: List[PageExtraction] = field(default_factory=list)
    invoice_data: Optional[InvoiceFields] = None
    line_items: List[LineItem] = field(default_factory=list)
    validation: ValidationResult = field(default_factory=ValidationResult)
    status: ProcessingStatus = ProcessingStatus.SUCCESS
    user_reviewed: bool = False
    user_overrides: Dict[str, Any] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "document_id": self.document_id,
            "filename": self.filename,
            "metadata": self.metadata.to_dict(),
            "classification": self.classification.to_dict(),
            "extraction_method": self.extraction_method,
            "pages": [p.to_dict() for p in self.pages],
            "invoice_data": self.invoice_data.to_dict() if self.invoice_data else None,
            "line_items": [item.to_dict() for item in self.line_items],
            "validation": self.validation.to_dict(),
            "status": self.status.value,
            "user_reviewed": self.user_reviewed,
            "user_overrides": self.user_overrides,
            "errors": self.errors
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, default=str)
