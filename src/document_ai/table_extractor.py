"""
Table and Line Item Extractor.
Identifies invoice item tables, header delimiters, and extracts individual
line item rows with description, quantity, unit price, and line totals.
"""

import re
from typing import List, Optional
from document_ai.layout_analyzer import TextLine, segment_into_lines
from document_ai.logging_config import get_logger
from document_ai.normalizer import normalize_amount
from document_ai.schemas import LineItem, PageExtraction

logger = get_logger("table_extractor")

# Table header keywords
HEADER_DESC_CUES = [r"\bdescription\b", r"\bitem\b", r"\bdetails\b", r"\bservice\b", r"\bproduct\b"]
HEADER_QTY_CUES = [r"\bqty\b", r"\bquantity\b", r"\bhours\b", r"\bhrs\b", r"\bunits\b"]
HEADER_PRICE_CUES = [r"\brate\b", r"\bunit\s*price\b", r"\bprice\b", r"\bcost\b"]
HEADER_TOTAL_CUES = [r"\bamount\b", r"\bline\s*total\b", r"\btotal\b"]

# Table termination cues
TERMINATION_PATTERNS = [
    r"\bsub\s*total\b",
    r"\btotal\s*due\b",
    r"\bamount\s+due\b",
    r"\bgrand\s+total\b",
    r"^\s*total\b",
    r"^\s*tax\b",
    r"^\s*vat\b",
    r"^\s*balance\s+due\b",
    r"\bpayment\s+(?:information|info|details|instructions)\b",
    r"^\s*notes?\b",
    r"^\s*thank\s+you\b",
    r"^\s*remittance\b",
]


def is_header_line(text: str) -> bool:
    """Checks if a line contains at least two column header indicators."""
    lower = text.lower()
    matches = 0
    if any(re.search(p, lower) for p in HEADER_DESC_CUES):
        matches += 1
    if any(re.search(p, lower) for p in HEADER_QTY_CUES):
        matches += 1
    if any(re.search(p, lower) for p in HEADER_PRICE_CUES):
        matches += 1
    if any(re.search(p, lower) for p in HEADER_TOTAL_CUES):
        matches += 1
    return matches >= 2


def is_termination_line(text: str) -> bool:
    """Checks if the line signals the end of the line item table."""
    lower = text.lower()
    return any(re.search(p, lower) for p in TERMINATION_PATTERNS)


def parse_line_item(line: TextLine) -> Optional[LineItem]:
    """
    Attempts to extract (Description, Quantity, Unit Price, Line Total)
    from a single tabular text row.
    Supports formats like:
    - Description ... Qty Price Total (e.g. 'Cloud Hosting 2 50.00 100.00')
    - Pipe-separated or tab-separated tables
    - Description followed by price and total
    """
    raw_text = line.text

    # Skip table header lines or separator lines like '---' or '==='
    if is_header_line(raw_text) or is_termination_line(raw_text):
        return None
    if re.match(r"^[\-_=\s\.\*\|]+$", raw_text):
        return None

    # Handle pipe-separated rows: "| Item | Qty | Rate | Total |"
    if "|" in raw_text:
        parts = [p.strip() for p in raw_text.split("|") if p.strip()]
        if len(parts) >= 2:
            desc = parts[0]
            # Try parsing remaining columns
            numeric_parts = [normalize_amount(p) for p in parts[1:]]
            nums = [n for n in numeric_parts if n is not None]
            if len(nums) == 3:
                # Qty, Unit Price, Total
                return LineItem(
                    description=desc,
                    quantity=nums[0],
                    unit_price=nums[1],
                    line_total=nums[2],
                    page_number=line.page_number,
                    raw_text=raw_text,
                    confidence=1.0 if abs(round(nums[0] * nums[1], 2) - nums[2]) < 0.05 else 0.8,
                )
            elif len(nums) == 2:
                # Qty or Price, and Total
                return LineItem(
                    description=desc,
                    quantity=nums[0] if nums[0] < 1000 and float(nums[0]).is_integer() else None,
                    unit_price=nums[0] if not float(nums[0]).is_integer() else None,
                    line_total=nums[1],
                    page_number=line.page_number,
                    raw_text=raw_text,
                    confidence=0.85,
                )
            elif len(nums) == 1:
                return LineItem(
                    description=desc,
                    line_total=nums[0],
                    page_number=line.page_number,
                    raw_text=raw_text,
                    confidence=0.75,
                )

    # 1. Smart token-based arithmetic parser for varied column layouts (e.g. OCR images)
    # Extracts all numbers/percentages and discovers columns by relationship (price * qty == total)
    token_pattern = re.compile(r"([\$€£₹]?\s*\d+(?:[\s,]\d{3})*(?:\.\d+)?%?)")
    matches = [m for m in token_pattern.finditer(raw_text) if m.group(0).strip()]
    if len(matches) >= 2:
        first_num_start = matches[0].start()
        desc = raw_text[:first_num_start].strip()
        if len(desc) >= 2 and not desc.isdigit() and not any(sym in desc for sym in ("$", "€", "£", "₹")):
            num_strings = [m.group(0).strip() for m in matches]
            numbers = []
            is_percent = []
            for s in num_strings:
                has_pct = "%" in s
                val = normalize_amount(s.replace("%", ""))
                if val is not None:
                    numbers.append(val)
                    is_percent.append(has_pct)

            if len(numbers) >= 2:
                total_val = numbers[-1]
                qty = None
                unit_price = None
                tax_rate = None

                # Disambiguate quantity and price by checking multiplication
                for i, a in enumerate(numbers[:-1]):
                    for j, b in enumerate(numbers[:-1]):
                        if i != j and abs(round(a * b, 2) - total_val) < 0.05:
                            if b.is_integer() and b <= 1000 and not a.is_integer():
                                qty, unit_price = b, a
                            elif a.is_integer() and a <= 1000 and not b.is_integer():
                                qty, unit_price = a, b
                            else:
                                qty, unit_price = min(a, b), max(a, b)
                            break
                    if qty is not None:
                        break

                for idx, p in enumerate(is_percent):
                    if p and idx < len(numbers):
                        tax_rate = numbers[idx]

                if qty is None:
                    if len(numbers) >= 3:
                        qty = numbers[0]
                        unit_price = numbers[1]
                    else:
                        unit_price = numbers[0]

                return LineItem(
                    description=desc,
                    quantity=qty,
                    unit_price=unit_price,
                    tax_rate=tax_rate,
                    line_total=total_val,
                    page_number=line.page_number,
                    raw_text=raw_text,
                    confidence=1.0 if (qty and unit_price and abs(round(qty * unit_price, 2) - total_val) < 0.05) else 0.85,
                )

    # 2. Regex search for numeric tokens at end of line: [Description] [qty] [rate] [total]
    num_token_pattern = re.compile(
        r"^(?P<desc>[^\$€£₹]+?)\s+"
        r"(?:(?P<qty>\d+(?:\.\d+)?)\s+)?"
        r"(?:[\$€£₹]?\s*(?P<price>\d[\d,\s]*\.\d{2})\s+)?"
        r"[\$€£₹]?\s*(?P<total>\d[\d,\s]*\.\d{2})$"
    )

    m = num_token_pattern.match(raw_text)
    if m:
        desc = m.group("desc").strip()
        if len(desc) < 2 or desc.isdigit():
            return None

        qty = float(m.group("qty")) if m.group("qty") else None
        unit_price = normalize_amount(m.group("price")) if m.group("price") else None
        total = normalize_amount(m.group("total"))

        confidence = 0.8
        if qty and unit_price and total:
            expected = round(qty * unit_price, 2)
            if abs(expected - total) < 0.05:
                confidence = 1.0
            else:
                confidence = 0.7

        return LineItem(
            description=desc,
            quantity=qty,
            unit_price=unit_price,
            line_total=total,
            page_number=line.page_number,
            raw_text=raw_text,
            confidence=confidence,
        )


def extract_table_items(pages: List[PageExtraction]) -> List[LineItem]:
    """
    Extracts all line items found within tabular structures across document pages.
    Detects table header boundaries and stops at table termination rows.
    """
    lines = segment_into_lines(pages)
    items: List[LineItem] = []
    in_table = False

    for line in lines:
        if is_header_line(line.text):
            in_table = True
            logger.debug(f"Detected table header at page {line.page_number}: '{line.text}'")
            continue

        if in_table:
            if is_termination_line(line.text):
                logger.debug(f"Reached table termination at page {line.page_number}: '{line.text}'")
                in_table = False
                continue

            parsed_item = parse_line_item(line)
            if parsed_item:
                items.append(parsed_item)

    # Fallback: if no explicit header was found, attempt line-by-line parsing
    # for clear (desc, qty, rate, total) rows
    if not items:
        for line in lines:
            if not is_termination_line(line.text) and not is_header_line(line.text):
                item = parse_line_item(line)
                # Require high confidence (qty * price == total) for headerless rows
                if item and item.confidence >= 0.95:
                    items.append(item)

    return items
