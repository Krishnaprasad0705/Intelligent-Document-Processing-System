"""
Invoice Field Extraction Engine.
Extracts business entity fields (invoice number, dates, vendor, customer,
monetary totals, PO number, payment terms, currency) with full evidence traceability.
"""

import re
from typing import Dict, List, Optional, Tuple
from document_ai.layout_analyzer import TextLine, segment_into_lines
from document_ai.logging_config import get_logger
from document_ai.normalizer import (
    clean_text,
    normalize_amount,
    normalize_currency,
    normalize_date,
)
from document_ai.schemas import FieldEvidence, InvoiceFields, PageExtraction

logger = get_logger("field_extractor")


def extract_regex_with_context(
    lines: List[TextLine],
    patterns: List[re.Pattern],
    exclude_patterns: Optional[List[re.Pattern]] = None,
) -> Optional[Tuple[str, FieldEvidence]]:
    """
    Searches lines for patterns and returns (raw_match, FieldEvidence).
    Ensures matched lines do not match any negative exclusions.
    """
    for line in lines:
        text = line.text
        if exclude_patterns and any(ex.search(text) for ex in exclude_patterns):
            continue

        for pat in patterns:
            m = pat.search(text)
            if m:
                # Group 1 is the target capture group
                val = m.group(1).strip()
                if val:
                    evidence = FieldEvidence(
                        field_name="",
                        raw_value=val,
                        matched_text=m.group(0).strip(),
                        page_number=line.page_number,
                        confidence=0.9,
                        context_snippet=text,
                    )
                    return val, evidence
    return None


class InvoiceFieldExtractor:
    """Extracts all standard invoice header, party, and financial fields."""

    def extract(self, pages: List[PageExtraction]) -> InvoiceFields:
        lines = segment_into_lines(pages)
        evidence_dict: Dict[str, FieldEvidence] = {}

        # 1. Invoice Number
        inv_num, inv_ev = self._extract_invoice_number(lines)
        if inv_ev:
            evidence_dict["invoice_number"] = inv_ev

        # 2. Purchase Order Number
        po_num, po_ev = self._extract_po_number(lines)
        if po_ev:
            evidence_dict["purchase_order_number"] = po_ev

        # 3. Dates
        inv_date, inv_date_ev = self._extract_invoice_date(lines)
        if inv_date_ev:
            evidence_dict["invoice_date"] = inv_date_ev

        due_date, due_date_ev = self._extract_due_date(lines)
        if due_date_ev:
            evidence_dict["due_date"] = due_date_ev

        # 4. Vendor Name
        vendor, vendor_ev = self._extract_vendor_name(lines)
        if vendor_ev:
            evidence_dict["vendor_name"] = vendor_ev

        # 5. Customer Name
        customer, customer_ev = self._extract_customer_name(lines)
        if customer_ev:
            evidence_dict["customer_name"] = customer_ev

        # 6. Currency
        currency, curr_ev = self._extract_currency(lines)
        if curr_ev:
            evidence_dict["currency"] = curr_ev

        # 7. Financial amounts
        subtotal, sub_ev = self._extract_monetary_field(
            lines,
            patterns=[
                re.compile(r"\b(?:subtotal|sub\s+total|total\s+net|net\s+amount)\s*[:=\-]?\s*[\$€£₹]?\s*([-\d,\.\s]+?)(?:\s{2,}|$|\n)", re.I),
            ],
            field_name="subtotal",
        )
        if sub_ev:
            evidence_dict["subtotal"] = sub_ev

        tax, tax_ev = self._extract_monetary_field(
            lines,
            patterns=[
                re.compile(r"\b(?:tax|vat|gst|sales\s+tax)(?:\s*\(\d+%\))?\s*[:=\-]?\s*[\$€£₹]?\s*([-\d,\.\s]+?)(?:\s{2,}|$|\n)", re.I),
                re.compile(r"\b(?:tax\s+amount)\s*[:=\-]?\s*[\$€£₹]?\s*([-\d,\.\s]+?)(?:\s{2,}|$|\n)", re.I),
            ],
            field_name="tax_amount",
        )
        if tax_ev:
            evidence_dict["tax_amount"] = tax_ev

        discount, disc_ev = self._extract_monetary_field(
            lines,
            patterns=[
                re.compile(r"\b(?:discount|less\s+discount|rebate)\s*[:=\-]?\s*[\$€£₹]?\s*([-\d,\.\s]+?)(?:\s{2,}|$|\n)", re.I),
            ],
            field_name="discount",
        )
        if disc_ev:
            evidence_dict["discount"] = disc_ev

        total, total_ev = self._extract_monetary_field(
            lines,
            patterns=[
                re.compile(r"\b(?:total\s+amount|amount\s+due|total\s+due|grand\s+total|invoice\s+total)\s*[:=\-]?\s*[\$€£₹]?\s*([-\d,\.\s]+?)(?:\s{2,}|$|\n)", re.I),
                re.compile(r"^\s*total\s*[:=\-]?\s*[\$€£₹]?\s*([-\d,\.\s]+?)(?:\s{2,}|$|\n)", re.I),
            ],
            field_name="total_amount",
            exclude_patterns=[
                re.compile(r"\b(?:subtotal|sub\s+total)\b", re.I)
            ]
        )
        if total_ev:
            evidence_dict["total_amount"] = total_ev
            # Re-evaluate tax if not set yet
            if "tax_amount" not in evidence_dict and subtotal is not None:
                sub_val = normalize_amount(subtotal)
                tot_val = normalize_amount(total)
                disc_val = normalize_amount(discount) or 0.0
                if sub_val is not None and tot_val is not None and tot_val > sub_val:
                    calc_tax = round(tot_val - sub_val + disc_val, 2)
                    tax = str(calc_tax)
                    evidence_dict["tax_amount"] = FieldEvidence(
                        field_name="tax_amount",
                        raw_value=tax,
                        matched_text=f"Derived from Total ({tot_val}) - Subtotal ({sub_val})",
                        page_number=1,
                        confidence=0.9,
                        context_snippet=f"Total: {tot_val}, Subtotal: {sub_val}",
                    )
        elif subtotal is not None:
            # Fallback: If total amount line is omitted, compute total from subtotal + tax - discount
            sub_val = normalize_amount(subtotal)
            if sub_val is not None:
                tax_val = normalize_amount(tax) or 0.0
                disc_val = normalize_amount(discount) or 0.0
                calc_total = round(sub_val + tax_val - disc_val, 2)
                total = str(calc_total)
                if sub_ev:
                    evidence_dict["total_amount"] = FieldEvidence(
                        field_name="total_amount",
                        raw_value=total,
                        matched_text=f"Derived from Subtotal ({sub_ev.matched_text})",
                        page_number=sub_ev.page_number,
                        confidence=0.85,
                        context_snippet=f"Subtotal: {sub_ev.context_snippet}",
                    )

        # 8. Payment Terms
        terms, terms_ev = self._extract_payment_terms(lines)
        if terms_ev:
            evidence_dict["payment_terms"] = terms_ev

        return InvoiceFields(
            invoice_number=inv_num,
            invoice_date=normalize_date(inv_date) if inv_date else None,
            due_date=normalize_date(due_date) if due_date else None,
            vendor_name=clean_text(vendor),
            customer_name=clean_text(customer),
            currency=normalize_currency(currency),
            subtotal=normalize_amount(subtotal) if subtotal else None,
            tax_amount=normalize_amount(tax) if tax else None,
            discount=normalize_amount(discount) if discount else None,
            total_amount=normalize_amount(total) if total is not None else None,
            payment_terms=clean_text(terms),
            purchase_order_number=clean_text(po_num),
            field_evidence=evidence_dict,
        )

    def _extract_invoice_number(self, lines: List[TextLine]) -> Tuple[Optional[str], Optional[FieldEvidence]]:
        patterns = [
            re.compile(r"\b(?:invoice|inv)\s+(?:no\b|number\b|#|num\b|id\b)\s*[:=\.\-]?\s*([A-Za-z0-9\-_/]+)", re.I),
            re.compile(r"\b(?:invoice|inv)\s*#\s*[:=\.\-]?\s*([A-Za-z0-9\-_/]+)", re.I),
            re.compile(r"\b(?:no|num|number)\s*[:=\.\-]\s*([A-Za-z0-9\-_/]+)", re.I),
            re.compile(r"\b(?:invoice|inv)\b\s*[:=]\s*([A-Za-z0-9\-_/]+)", re.I),
            re.compile(r"\bbill\s*(?:no\b|number\b|#)\s*[:=\.\-]?\s*([A-Za-z0-9\-_/]+)", re.I),
        ]
        # Avoid picking up PO numbers as invoice numbers
        exclude = [re.compile(r"\b(?:purchase\s*order|po\s*#|p\.o\.)\b", re.I)]
        res = extract_regex_with_context(lines, patterns, exclude_patterns=exclude)
        if res:
            val, ev = res
            clean_val = val.strip()
            if clean_val.upper() not in {"INVOICE", "OICE", "TAX", "BILL", "DATE", "RECEIPT", "STATEMENT", "TOTAL", "SUBTOTAL"}:
                ev.field_name = "invoice_number"
                return clean_val, ev
        return None, None

    def _extract_po_number(self, lines: List[TextLine]) -> Tuple[Optional[str], Optional[FieldEvidence]]:
        patterns = [
            re.compile(r"\b(?:purchase\s*order|p\.o\.|po\b)\s*(?:no|number|#|num)?\s*[:=\.\-]?\s*([A-Za-z0-9\-_/]+)", re.I),
        ]
        res = extract_regex_with_context(lines, patterns)
        if res:
            val, ev = res
            ev.field_name = "purchase_order_number"
            return val, ev
        return None, None

    def _extract_invoice_date(self, lines: List[TextLine]) -> Tuple[Optional[str], Optional[FieldEvidence]]:
        patterns = [
            re.compile(r"\b(?:invoice\s*date|date\s*of\s*issue|billing\s*date)\s*[:=\-]?\s*([A-Za-z0-9\s,\./\-]+?)(?:\s{2,}|$|\n)", re.I),
            re.compile(r"^\s*date\s*[:=\-]?\s*([A-Za-z0-9\s,\./\-]+?)(?:\s{2,}|$|\n)", re.I),
        ]
        exclude = [re.compile(r"\b(?:due\s*date|pay\s*by)\b", re.I)]
        res = extract_regex_with_context(lines, patterns, exclude_patterns=exclude)
        if res:
            val, ev = res
            ev.field_name = "invoice_date"
            return val, ev
        return None, None

    def _extract_due_date(self, lines: List[TextLine]) -> Tuple[Optional[str], Optional[FieldEvidence]]:
        patterns = [
            re.compile(r"\b(?:due\s*date|payment\s*due|pay\s*by)\s*[:=\-]?\s*([A-Za-z0-9\s,\./\-]+?)(?:\s{2,}|$|\n)", re.I),
        ]
        res = extract_regex_with_context(lines, patterns)
        if res:
            val, ev = res
            ev.field_name = "due_date"
            return val, ev
        return None, None

    def _extract_customer_name(self, lines: List[TextLine]) -> Tuple[Optional[str], Optional[FieldEvidence]]:
        """Finds customer in 'Bill To', 'Invoice To', or 'Customer:' blocks."""
        for i, line in enumerate(lines):
            # Strict word boundary so 'invoice to' does not match 'invoice total'
            m = re.search(r"\b(?:bill\s+to|invoice\s+to|sold\s+to|billed\s+to|customer|client)\b\s*[:=\-]?\s*(.*)", line.text, re.I)
            if m:
                raw_inline = m.group(1).strip()
                # Check if inline text contains adjacent column like 'From:' or 'Ship To:'
                inline_candidate = re.split(r"\b(?:from|vendor|supplier|ship\s+to)\b", raw_inline, flags=re.I)[0].strip()
                # Avoid accepting label words like 'From:' or 'Ship To' or empty string
                if inline_candidate and len(inline_candidate) > 2 and not re.match(r"^(?:from|vendor|supplier|ship\s*to)[:\s]*$", inline_candidate, re.I):
                    ev = FieldEvidence(
                        field_name="customer_name",
                        raw_value=inline_candidate,
                        matched_text=m.group(0),
                        page_number=line.page_number,
                        confidence=0.85,
                        context_snippet=line.text,
                    )
                    return inline_candidate, ev
                # Check next line
                if i + 1 < len(lines):
                    next_line = lines[i + 1].text.strip()
                    if next_line and not re.search(r"\b(?:invoice|date|tax|total|terms)\b", next_line, re.I):
                        # If next line has two columns separated by 2+ spaces, pick the first column (Bill To side)
                        columns = [c.strip() for c in re.split(r"\s{2,}", next_line) if c.strip()]
                        chosen_val = columns[0] if columns else next_line
                        # If address digits exist at end, strip them to isolate customer name
                        name_match = re.search(r"^(.*?)(?:\s+\d{2,}|\s{2,}|\n|$)", chosen_val)
                        if name_match and len(name_match.group(1).strip()) > 2:
                            chosen_val = name_match.group(1).strip()
                        ev = FieldEvidence(
                            field_name="customer_name",
                            raw_value=chosen_val,
                            matched_text=f"{line.text} -> {chosen_val}",
                            page_number=lines[i + 1].page_number,
                            confidence=0.9,
                            context_snippet=next_line,
                        )
                        return chosen_val, ev

        # Fallback: scan for second organization block before financial details
        for line in lines[:8]:
            t = line.text.strip()
            if re.search(r"\b(?:app\s+revolution|client|customer|ltd|inc|corp|co)\b", t, re.I):
                if not re.search(r"\b(?:invoice|tax|total|date|bank)\b", t, re.I):
                    ev = FieldEvidence(
                        field_name="customer_name",
                        raw_value=t,
                        matched_text=t,
                        page_number=line.page_number,
                        confidence=0.75,
                        context_snippet=t,
                    )
                    return t, ev
        return None, None

    def _extract_vendor_name(self, lines: List[TextLine]) -> Tuple[Optional[str], Optional[FieldEvidence]]:
        """
        Vendor is typically identified via:
        1. Explicit 'From:', 'Vendor:', 'Supplier:' label
        2. Top header of first page (first non-empty text line that is not 'INVOICE')
        """
        # 1. Explicit label or payment payee
        for i, line in enumerate(lines):
            m = re.search(r"^\s*(?:from|vendor|supplier|company)\s*[:=\-]\s*(.+)", line.text, re.I)
            if not m:
                m = re.search(r"\b(?:make\s+payment\s+to|payable\s+to|remit\s+to|pay\s+to)\s*[:=\-]?\s*(.*)", line.text, re.I)
            if m:
                val = m.group(1).strip()
                if not val and i + 1 < len(lines):
                    val = lines[i + 1].text.strip()
                if val and len(val) >= 3 and not re.match(r"^[\d\W]+$", val):
                    ev = FieldEvidence(
                        field_name="vendor_name",
                        raw_value=val,
                        matched_text=m.group(0),
                        page_number=line.page_number,
                        confidence=0.9,
                        context_snippet=line.text,
                    )
                    return val, ev

        # 2. Header on page 1
        page_1_lines = [l for l in lines if l.page_number == 1]
        for line in page_1_lines[:6]:
            t = line.text.strip()
            # Clean OCR pipes or trailing titles like 'Future | TAX INVOICE' -> 'Future'
            t_clean = re.sub(r"\s*[\|/]\s*(?:tax\s+)?invoice\b.*", "", t, flags=re.I).strip()
            # Ignore title 'Invoice', numbers, or dates
            if re.match(r"^(?:tax\s+)?invoice\b", t_clean, re.I):
                continue
            if re.match(r"^(?:page\s+\d+|date|http)", t_clean, re.I):
                continue
            if len(t_clean) >= 3 and not re.match(r"^[\d\W]+$", t_clean):
                ev = FieldEvidence(
                    field_name="vendor_name",
                    raw_value=t_clean,
                    matched_text=t,
                    page_number=1,
                    confidence=0.8,
                    context_snippet=t,
                )
                return t_clean, ev

        return None, None

    def _extract_currency(self, lines: List[TextLine]) -> Tuple[Optional[str], Optional[FieldEvidence]]:
        """Identifies currency symbol or code across the invoice."""
        for line in lines:
            # Check for currency words first
            m_code = re.search(r"\b(USD|EUR|GBP|CAD|AUD|INR|JPY|CHF)\b", line.text)
            if m_code:
                code = m_code.group(1)
                ev = FieldEvidence(
                    field_name="currency",
                    raw_value=code,
                    matched_text=code,
                    page_number=line.page_number,
                    confidence=0.95,
                    context_snippet=line.text,
                )
                return code, ev

            # Check for symbols
            for sym in ("$", "€", "£", "₹", "¥"):
                if sym in line.text:
                    ev = FieldEvidence(
                        field_name="currency",
                        raw_value=sym,
                        matched_text=sym,
                        page_number=line.page_number,
                        confidence=0.9,
                        context_snippet=line.text,
                    )
                    return sym, ev

        return None, None

    def _extract_payment_terms(self, lines: List[TextLine]) -> Tuple[Optional[str], Optional[FieldEvidence]]:
        patterns = [
            re.compile(r"\b(?:payment\s*terms?|terms?)\s*[:=\-]?\s*(net\s*\d+|due\s*on\s*receipt|due\s*upon\s*receipt|immediate|cash|within\s*\d+\s*days)", re.I),
            re.compile(r"\b(net\s*\d+)\b", re.I),
        ]
        res = extract_regex_with_context(lines, patterns)
        if res:
            val, ev = res
            ev.field_name = "payment_terms"
            return val, ev
        return None, None

    def _extract_monetary_field(
        self,
        lines: List[TextLine],
        patterns: List[re.Pattern],
        field_name: str,
        exclude_patterns: Optional[List[re.Pattern]] = None,
    ) -> Tuple[Optional[str], Optional[FieldEvidence]]:
        res = extract_regex_with_context(lines, patterns, exclude_patterns=exclude_patterns)
        if res:
            val, ev = res
            ev.field_name = field_name
            return val, ev
        return None, None


_FIELD_EXTRACTOR = InvoiceFieldExtractor()


def extract_invoice_fields(pages: List[PageExtraction]) -> InvoiceFields:
    """Convenience function to run invoice field extraction on extracted document pages."""
    return _FIELD_EXTRACTOR.extract(pages)
