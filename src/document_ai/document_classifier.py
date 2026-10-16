"""
Document Classifier.
Rule-based, explainable scoring engine that categorizes documents into
Invoice, Receipt, Purchase Order, Contract, Business Report, or Unknown.
Returns clear evidence, confidence scores, and human review flags.
"""

import re
from typing import Dict, List, Tuple
from document_ai.logging_config import get_logger
from document_ai.schemas import (
    ClassificationEvidence,
    DocumentClassification,
    DocumentType,
    PageExtraction,
)

logger = get_logger("document_classifier")

# Cue patterns with descriptive names and calibrated weights
CLASSIFICATION_CUES: Dict[DocumentType, List[Tuple[str, float, str]]] = {
    DocumentType.INVOICE: [
        (r"\b(tax\s+)?invoice\b", 2.5, "Explicit 'invoice' header"),
        (r"\binvoice\s*(no|number|#|num)\b", 2.0, "Invoice number label"),
        (r"\bbill\s+to\b", 1.8, "'Bill To' section"),
        (r"\bdue\s+date\b", 1.5, "'Due Date' header"),
        (r"\bamount\s+due\b", 1.5, "'Amount Due' statement"),
        (r"\bsubtotal\b", 1.0, "'Subtotal' row"),
        (r"\bremittance\b", 1.2, "'Remittance' instruction"),
        (r"\bpayment\s+terms\b", 1.2, "'Payment Terms' label"),
    ],
    DocumentType.RECEIPT: [
        (r"\breceipt\b", 2.5, "Explicit 'receipt' title"),
        (r"\bcashier\b", 2.0, "Cashier designation"),
        (r"\b(register|pos|terminal)\s*#?\d*", 1.8, "Point-of-sale / register reference"),
        (r"\bchange\s+due\b", 2.0, "'Change Due' line"),
        (r"\bitems?\s+sold\b", 1.2, "Items sold counter"),
        (r"\bthank\s+you\s+for\s+(shopping|your\s+visit)\b", 1.5, "Retail customer greeting"),
    ],
    DocumentType.PURCHASE_ORDER: [
        (r"\bpurchase\s+order\b", 2.5, "Explicit 'Purchase Order' title"),
        (r"\b(po|p\.o\.)\s*(no|number|#)\b", 2.2, "PO number identifier"),
        (r"\bvendor\s+order\b", 1.5, "Vendor order label"),
        (r"\bship\s+to\b", 1.5, "'Ship To' delivery address"),
        (r"\brequisition\s*(no|#)?\b", 1.8, "Requisition number"),
        (r"\border\s+placed\s+by\b", 1.5, "Buyer ordering agent"),
    ],
    DocumentType.CONTRACT: [
        (r"\b(this\s+)?agreement\b", 2.0, "'Agreement' legal declaration"),
        (r"\bwhereas\b", 2.2, "Legal 'Whereas' recital clauses"),
        (r"\bin\s+witness\s+whereof\b", 2.5, "Signature clause 'In Witness Whereof'"),
        (r"\bterms\s+and\s+conditions\b", 1.5, "Standard terms & conditions section"),
        (r"\bgoverning\s+law\b", 1.8, "Jurisdiction / governing law clause"),
        (r"\bindemnification\b", 1.8, "Indemnity legal clause"),
        (r"\bthe\s+parties\s+(hereto\s+)?agree\b", 1.8, "Legal covenant statement"),
    ],
    DocumentType.BUSINESS_REPORT: [
        (r"\bexecutive\s+summary\b", 2.5, "'Executive Summary' heading"),
        (r"\b(quarterly|annual)\s+report\b", 2.5, "Report periodicity header"),
        (r"\btable\s+of\s+contents\b", 2.0, "'Table of Contents' page"),
        (r"\bkey\s+findings\b", 1.8, "'Key Findings' section"),
        (r"\bmethodology\b", 1.5, "'Methodology' section"),
        (r"\bconclusion\s+and\s+recommendations\b", 2.0, "Conclusions/recommendations section"),
    ],
}


class DocumentClassifier:
    """Explainable rule-based classifier for business documents."""

    def __init__(self, confidence_threshold: float = 2.5, margin_threshold: float = 0.8) -> None:
        self.confidence_threshold = confidence_threshold
        self.margin_threshold = margin_threshold

    def classify(self, pages: List[PageExtraction]) -> DocumentClassification:
        """
        Classifies document pages by evaluating cue patterns across all pages.
        Returns predicted type, confidence, evidence items, and review indicator.
        """
        if not pages:
            return DocumentClassification(
                predicted_type=DocumentType.UNKNOWN,
                confidence=0.0,
                evidence=[],
                requires_human_review=True,
                score_breakdown={},
            )

        raw_scores: Dict[DocumentType, float] = {doc_type: 0.0 for doc_type in CLASSIFICATION_CUES}
        evidence_list: List[ClassificationEvidence] = []

        # Analyze each page
        for page in pages:
            text_lower = page.text.lower()
            if not text_lower.strip():
                continue

            for doc_type, cues in CLASSIFICATION_CUES.items():
                for pattern, weight, cue_desc in cues:
                    matches = list(re.finditer(pattern, text_lower, re.IGNORECASE))
                    if matches:
                        match_count = min(len(matches), 3)  # Diminishing returns for repeated cues
                        added_score = weight * (1.0 + 0.25 * (match_count - 1))
                        raw_scores[doc_type] += added_score

                        # Record evidence from the first match
                        m = matches[0]
                        start = max(0, m.start() - 20)
                        end = min(len(page.text), m.end() + 20)
                        snippet = page.text[start:end].replace("\n", " ").strip()

                        evidence_list.append(
                            ClassificationEvidence(
                                cue=f"{doc_type.value}: {cue_desc}",
                                weight=round(added_score, 2),
                                matched_text=snippet,
                                page_number=page.page_number,
                            )
                        )

        # Sort raw scores
        sorted_scores = sorted(raw_scores.items(), key=lambda item: item[1], reverse=True)
        top_type, top_score = sorted_scores[0]
        second_type, second_score = sorted_scores[1]

        score_breakdown = {k.value: round(v, 2) for k, v in raw_scores.items()}

        # Check threshold for UNKNOWN
        if top_score < self.confidence_threshold:
            logger.info(f"Top score {top_score:.2f} below threshold {self.confidence_threshold}. Marking UNKNOWN.")
            return DocumentClassification(
                predicted_type=DocumentType.UNKNOWN,
                confidence=round(min(top_score / self.confidence_threshold, 0.49), 2),
                evidence=evidence_list,
                requires_human_review=True,
                score_breakdown=score_breakdown,
            )

        # Calculate normalized confidence
        score_diff = top_score - second_score
        # High confidence when top score is strong and distinct from runner-up
        base_confidence = min(0.95, 0.5 + (top_score / 15.0))
        requires_review = False

        if score_diff < self.margin_threshold:
            # Ambiguous document between top two categories
            logger.info(f"Ambiguous classification between {top_type} ({top_score}) and {second_type} ({second_score})")
            requires_review = True
            base_confidence = max(0.5, base_confidence - 0.2)

        return DocumentClassification(
            predicted_type=top_type,
            confidence=round(base_confidence, 2),
            evidence=evidence_list,
            requires_human_review=requires_review,
            score_breakdown=score_breakdown,
        )


_CLASSIFIER_INSTANCE = DocumentClassifier()


def classify_document(pages: List[PageExtraction]) -> DocumentClassification:
    """Utility function to classify document pages."""
    return _CLASSIFIER_INSTANCE.classify(pages)
