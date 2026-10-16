"""
Data Normalization Layer.
Normalizes extracted raw strings into standardized data types:
- ISO 8601 dates (YYYY-MM-DD)
- Floating-point monetary values with proper decimal/thousands handling
- Standard ISO 4217 3-letter currency codes
- Clean sanitized strings
"""

from datetime import datetime
import re
from typing import Optional, Tuple


# Currency symbol and code mapping to ISO-4217
CURRENCY_MAP = {
    "$": "USD",
    "US$": "USD",
    "USD": "USD",
    "€": "EUR",
    "EUR": "EUR",
    "£": "GBP",
    "GBP": "GBP",
    "¥": "JPY",
    "JPY": "JPY",
    "CNY": "CNY",
    "₹": "INR",
    "INR": "INR",
    "RS": "INR",
    "RS.": "INR",
    "CAD": "CAD",
    "AUD": "AUD",
    "CHF": "CHF",
}

MONTH_NAMES = {
    "jan": 1, "january": 1,
    "feb": 2, "february": 2,
    "mar": 3, "march": 3,
    "apr": 4, "april": 4,
    "may": 5,
    "jun": 6, "june": 6,
    "jul": 7, "july": 7,
    "aug": 8, "august": 8,
    "sep": 9, "sept": 9, "september": 9,
    "oct": 10, "october": 10,
    "nov": 11, "november": 11,
    "dec": 12, "december": 12,
}


def clean_text(raw_text: Optional[str]) -> Optional[str]:
    """Strips leading/trailing whitespace and collapses inner spaces."""
    if raw_text is None:
        return None
    cleaned = re.sub(r"\s+", " ", raw_text).strip()
    return cleaned if cleaned else None


def normalize_currency(raw_currency: Optional[str]) -> Optional[str]:
    """Normalizes raw currency symbol or name to standard 3-letter ISO code."""
    if not raw_currency:
        return None
    cleaned = raw_currency.strip().upper()
    # Check exact symbol or code
    if cleaned in CURRENCY_MAP:
        return CURRENCY_MAP[cleaned]
    # Check if raw string contains any known symbol or code
    for symbol, iso in CURRENCY_MAP.items():
        if symbol in raw_currency:
            return iso
    return cleaned if len(cleaned) == 3 and cleaned.isalpha() else None


def normalize_amount(raw_amount: Optional[str]) -> Optional[float]:
    """
    Parses strings representing numbers/monetary amounts into a clean float.
    Handles:
    - 1,234.56 or 1234.56
    - 1.234,56 (European style)
    - ($123.45) or -$123.45 for negative amounts
    - Trailing minus signs: 123.45-
    """
    if raw_amount is None:
        return None

    s = str(raw_amount).strip()
    if not s:
        return None

    # Check negative format
    is_negative = False
    if s.startswith("(") and s.endswith(")"):
        is_negative = True
        s = s[1:-1].strip()
    elif s.startswith("-"):
        is_negative = True
        s = s[1:].strip()
    elif s.endswith("-"):
        is_negative = True
        s = s[:-1].strip()

    # Strip currency symbols and letters
    s = re.sub(r"[^\d,\.]", "", s).strip()
    if not s:
        return None

    # Determine decimal and thousands separator
    if "," in s and "." in s:
        # Check which one appears last
        if s.rfind(".") > s.rfind(","):
            # Standard US style: 1,234.56
            s = s.replace(",", "")
        else:
            # European style: 1.234,56
            s = s.replace(".", "").replace(",", ".")
    elif "," in s and "." not in s:
        # Could be 1,234 or 12,34
        parts = s.split(",")
        if len(parts) == 2 and len(parts[1]) == 2:
            # European decimal: 12,34 -> 12.34
            s = s.replace(",", ".")
        else:
            # Thousands: 1,234 -> 1234
            s = s.replace(",", "")

    try:
        val = float(s)
        if is_negative:
            val = -val
        return round(val, 2)
    except ValueError:
        return None


def normalize_date(raw_date: Optional[str]) -> Optional[str]:
    """
    Normalizes a variety of date formats into ISO 8601 YYYY-MM-DD.
    Handles OCR digit confusion where letter 'O' or 'o' is misread for '0'.
    Returns None if date cannot be resolved or is invalid.
    """
    if not raw_date:
        return None

    clean = raw_date.strip()
    # Correct OCR misreading of letter O/o instead of digit 0
    clean = re.sub(r"\b[Oo](\d+)\b", r"\1", clean)
    clean = re.sub(r"\b[Oo](?=\d)", "0", clean)
    clean = re.sub(r"(?<=\d)[Oo]\b", "0", clean)

    # 1. Standard ISO formats
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d"):
        try:
            return datetime.strptime(clean, fmt).strftime("%Y-%m-%d")
        except ValueError:
            pass

    # 2. Textual month formats: "March 15, 2024", "15-Mar-2024", "15 March 2024"
    # Remove ordinal suffixes (15th, 1st, 2nd, 3rd)
    clean_ord = re.sub(r"(\d+)(st|nd|rd|th)\b", r"\1", clean, flags=re.IGNORECASE)
    for fmt in (
        "%B %d, %Y", "%b %d, %Y",
        "%d %B %Y", "%d %b %Y",
        "%d-%b-%Y", "%d-%B-%Y",
        "%d/%b/%Y", "%b %d %Y",
        "%B %d %Y"
    ):
        try:
            return datetime.strptime(clean_ord, fmt).strftime("%Y-%m-%d")
        except ValueError:
            pass

    # 3. Numeric patterns like DD/MM/YYYY or MM/DD/YYYY
    match = re.search(r"(\d{1,2})[/\-\.](\d{1,2})[/\-\.](\d{2,4})", clean)
    if match:
        p1, p2, p3 = int(match.group(1)), int(match.group(2)), int(match.group(3))
        # Handle 2-digit year
        if p3 < 100:
            year = 2000 + p3 if p3 < 70 else 1900 + p3
        else:
            year = p3

        # Disambiguate DD/MM vs MM/DD
        if p1 > 12 >= p2:
            # p1 must be day, p2 is month
            day, month = p1, p2
        elif p2 > 12 >= p1:
            # p2 must be day, p1 is month
            month, day = p1, p2
        else:
            # Ambiguous (e.g. 05/06/2024) -> default to Day/Month/Year for international invoices
            day, month = p1, p2

        try:
            dt = datetime(year, month, day)
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            pass

    return None
