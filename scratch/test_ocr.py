import re
from typing import Optional
from document_ai.normalizer import normalize_amount
from document_ai.schemas import LineItem

def parse_line_item_intelligent(raw_text: str, page_number: int = 1) -> Optional[LineItem]:
    text = raw_text.strip()
    if not text:
        return None

    # Find where the numbers start
    # Match numbers like $150.00, 10, 10%, $1 500.00, 1,500.00
    # A numeric token starts with optional currency symbol and digits
    token_pattern = re.compile(r"([\$€£₹]?\s*\d+(?:[\s,]\d{3})*(?:\.\d+)?%?)")
    matches = list(token_pattern.finditer(text))
    if not matches:
        return None

    first_num_start = matches[0].start()
    desc = text[:first_num_start].strip()
    if len(desc) < 2 or desc.isdigit():
        return None

    num_strings = [m.group(0).strip() for m in matches if m.group(0).strip()]
    if not num_strings:
        return None

    # Parse numbers
    numbers = []
    is_percent = []
    for s in num_strings:
        has_pct = "%" in s
        val = normalize_amount(s.replace("%", ""))
        if val is not None:
            numbers.append(val)
            is_percent.append(has_pct)

    if not numbers:
        return None

    # If only 1 number, it's the line total
    if len(numbers) == 1:
        return LineItem(
            description=desc,
            line_total=numbers[0],
            page_number=page_number,
            raw_text=text,
            confidence=0.75,
        )

    # If multiple numbers, check arithmetic combinations:
    # Look for any pair (a, b) where round(a * b, 2) == c
    total_val = numbers[-1]
    qty = None
    unit_price = None
    tax_rate = None

    for i, a in enumerate(numbers[:-1]):
        for j, b in enumerate(numbers[:-1]):
            if i != j and abs(round(a * b, 2) - total_val) < 0.05:
                # One is quantity, one is unit price
                if a.is_integer() and not b.is_integer():
                    qty, unit_price = a, b
                elif b.is_integer() and not a.is_integer():
                    qty, unit_price = b, a
                else:
                    qty, unit_price = a, b
                break
        if qty is not None:
            break

    # Look for tax rate (e.g. 10%)
    for idx, p in enumerate(is_percent):
        if p and idx < len(numbers):
            tax_rate = numbers[idx]

    # Fallback if no exact multiplication matched
    if qty is None and len(numbers) >= 2:
        if len(numbers) >= 3:
            qty = numbers[0]
            unit_price = numbers[1]
            total_val = numbers[-1]
        else:
            unit_price = numbers[0]
            total_val = numbers[1]

    confidence = 1.0 if (qty and unit_price and abs(round(qty * unit_price, 2) - total_val) < 0.05) else 0.85

    return LineItem(
        description=desc,
        quantity=qty,
        unit_price=unit_price,
        tax_rate=tax_rate,
        line_total=total_val,
        page_number=page_number,
        raw_text=text,
        confidence=confidence,
    )

if __name__ == "__main__":
    t = "Design of new logo $150.00 10 10% $1 500.00"
    item = parse_line_item_intelligent(t)
    print("Parsed:", item)
