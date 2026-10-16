"""
Tests for normalization of dates, currencies, amounts, and text.
"""

from document_ai.normalizer import (
    clean_text,
    normalize_amount,
    normalize_currency,
    normalize_date,
)


def test_normalize_dates():
    assert normalize_date("2024-03-15") == "2024-03-15"
    assert normalize_date("2024/03/15") == "2024-03-15"
    assert normalize_date("March 15, 2024") == "2024-03-15"
    assert normalize_date("15-Mar-2024") == "2024-03-15"
    assert normalize_date("15th March 2024") == "2024-03-15"
    assert normalize_date("15/03/2024") == "2024-03-15"
    assert normalize_date("invalid date") is None
    assert normalize_date("") is None


def test_normalize_amounts():
    assert normalize_amount("1,234.50") == 1234.50
    assert normalize_amount("$1,234.50") == 1234.50
    assert normalize_amount("1.234,50 €") == 1234.50
    assert normalize_amount("500") == 500.0
    assert normalize_amount("($100.00)") == -100.0
    assert normalize_amount("-50.25") == -50.25
    assert normalize_amount("invalid") is None
    assert normalize_amount(None) is None


def test_normalize_currency():
    assert normalize_currency("$") == "USD"
    assert normalize_currency("USD") == "USD"
    assert normalize_currency("€") == "EUR"
    assert normalize_currency("EUR") == "EUR"
    assert normalize_currency("£") == "GBP"
    assert normalize_currency("GBP") == "GBP"
    assert normalize_currency("₹") == "INR"
    assert normalize_currency("INR") == "INR"
    assert normalize_currency(None) is None


def test_clean_text():
    assert clean_text("  ACME   Corp   \n  ") == "ACME Corp"
    assert clean_text("") is None
    assert clean_text(None) is None
