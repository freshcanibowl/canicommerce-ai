"""Synthetic-only payment parser tests; no PayPal network calls."""
import pytest
from canicommerce.payment_contract import ExpectedPayment, EvidenceError, parse_paypal_capture, parse_minor

EXPECTED = ExpectedPayment("ORDER-SYNTHETIC", 100, "USD", "MERCHANT-SYNTHETIC")

def fixture():
    return {
        "id": "CAPTURE-SYNTHETIC",
        "status": "COMPLETED",
        "amount": {"value": "1.00", "currency_code": "USD"},
        "supplementary_data": {"related_ids": {"order_id": "ORDER-SYNTHETIC"}},
    }

def parse(payload, order="ORDER-SYNTHETIC", merchant="MERCHANT-SYNTHETIC"):
    return parse_paypal_capture(payload, EXPECTED,
        authenticated_order_id=order, authenticated_merchant_id=merchant)

def test_synthetic_capture_is_not_authenticated():
    receipt = parse(fixture())
    assert receipt.amount_minor == 100
    assert receipt.evidence_level == "UNAUTHENTICATED_PAYLOAD_PARSED"

@pytest.mark.parametrize("field,value", [
    ("status", "PENDING"), ("status", "DENIED"), ("id", ""), ("amount", None),
])
def test_reject_invalid_top_level(field, value):
    p = fixture()
    p[field] = value
    with pytest.raises(EvidenceError):
        parse(p)

def test_wrong_amount():
    p = fixture(); p["amount"]["value"] = "2.00"
    with pytest.raises(EvidenceError): parse(p)

def test_wrong_currency():
    p = fixture(); p["amount"]["currency_code"] = "MYR"
    with pytest.raises(EvidenceError): parse(p)

def test_wrong_related_order():
    p = fixture(); p["supplementary_data"]["related_ids"]["order_id"] = "OTHER"
    with pytest.raises(EvidenceError): parse(p)

def test_wrong_trusted_order():
    with pytest.raises(EvidenceError): parse(fixture(), order="OTHER")

def test_wrong_trusted_merchant():
    with pytest.raises(EvidenceError): parse(fixture(), merchant="OTHER")

@pytest.mark.parametrize("value", ["NaN", "Infinity", "-1.00", "1.001", "nonsense"])
def test_invalid_amounts(value):
    with pytest.raises(EvidenceError): parse_minor(value, 2)

def test_invalid_expected_amount():
    with pytest.raises(EvidenceError): ExpectedPayment("x", True, "USD", "m")

def test_zero_decimal_currency():
    assert parse_minor("100", 0) == 100

def test_missing_capture_id():
    p = fixture(); del p["id"]
    with pytest.raises(EvidenceError): parse(p)
