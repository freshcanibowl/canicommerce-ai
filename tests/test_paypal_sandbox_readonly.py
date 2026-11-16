"""Mock transport tests; all identities and transactions synthetic."""
import copy
import pytest
from canicommerce.payment_contract import ExpectedPayment, EvidenceError
from canicommerce.paypal_sandbox_readonly import verify_sandbox_capture, verify_from_environment

EXPECTED = ExpectedPayment("ORDER_SYNTH", 100, "USD", "MERCHANT_SYNTH")

def responses():
    order = {"id": "ORDER_SYNTH", "status": "COMPLETED", "purchase_units": [{
        "payee": {"merchant_id": "MERCHANT_SYNTH"},
        "payments": {"captures": [{"id": "CAPTURE_SYNTH", "status": "COMPLETED",
                                    "amount": {"value": "1.00", "currency_code": "USD"}}]}
    }]}
    capture = {"id": "CAPTURE_SYNTH", "status": "COMPLETED",
               "amount": {"value": "1.00", "currency_code": "USD"},
               "supplementary_data": {"related_ids": {"order_id": "ORDER_SYNTH"}}}
    return order, capture

def fake_transport(order, capture, calls):
    def call(method, path, *, headers, data=None):
        calls.append((method, path))
        if path == "/v1/oauth2/token":
            assert method == "POST"
            return {"access_token": "SYNTHETIC_TOKEN"}
        assert method == "GET"
        if path == "/v2/checkout/orders/ORDER_SYNTH":
            return copy.deepcopy(order)
        if path == "/v2/payments/captures/CAPTURE_SYNTH":
            return copy.deepcopy(capture)
        raise AssertionError("unexpected endpoint")
    return call

def run(order=None, capture=None):
    original_order, original_capture = responses()
    calls = []
    result = verify_sandbox_capture(EXPECTED, client_id="fake", client_secret="fake",
        transport=fake_transport(order if order is not None else original_order,
                                 capture if capture is not None else original_capture, calls))
    return result, calls

def test_verified_synthetic_flow():
    result, calls = run()
    assert result.evidence_level == "PROVIDER_READBACK_SANDBOX"
    assert result.amount_minor == 100
    assert calls == [("POST", "/v1/oauth2/token"),
                     ("GET", "/v2/checkout/orders/ORDER_SYNTH"),
                     ("GET", "/v2/payments/captures/CAPTURE_SYNTH")]

@pytest.mark.parametrize("change", ["created", "orderid", "merchant", "two_units", "no_payee",
                                    "no_captures", "two_captures", "embedded_pending", "embedded_amount"])
def test_invalid_order_denied(change):
    order, capture = responses()
    unit = order["purchase_units"][0]
    if change == "created": order["status"] = "CREATED"
    if change == "orderid": order["id"] = "OTHER"
    if change == "merchant": unit["payee"]["merchant_id"] = "OTHER"
    if change == "two_units": order["purchase_units"].append(copy.deepcopy(unit))
    if change == "no_payee": del unit["payee"]
    if change == "no_captures": unit["payments"]["captures"] = []
    if change == "two_captures": unit["payments"]["captures"].append(copy.deepcopy(unit["payments"]["captures"][0]))
    if change == "embedded_pending": unit["payments"]["captures"][0]["status"] = "PENDING"
    if change == "embedded_amount": unit["payments"]["captures"][0]["amount"]["value"] = "2.00"
    with pytest.raises(EvidenceError):
        run(order=order, capture=capture)

@pytest.mark.parametrize("change", ["pending", "captureid", "amount", "currency", "related_order", "missingid"])
def test_invalid_capture_denied(change):
    order, capture = responses()
    if change == "pending": capture["status"] = "PENDING"
    if change == "captureid": capture["id"] = "OTHER"
    if change == "amount": capture["amount"]["value"] = "2.00"
    if change == "currency": capture["amount"]["currency_code"] = "MYR"
    if change == "related_order": capture["supplementary_data"]["related_ids"]["order_id"] = "OTHER"
    if change == "missingid": del capture["id"]
    with pytest.raises(EvidenceError):
        run(order=order, capture=capture)

def test_no_sandbox_mode_denied(monkeypatch):
    monkeypatch.delenv("PAYPAL_MODE", raising=False)
    with pytest.raises(EvidenceError):
        verify_from_environment(EXPECTED)

def test_credentials_required():
    with pytest.raises(EvidenceError):
        verify_sandbox_capture(EXPECTED, client_id="", client_secret="x",
            transport=lambda *args, **kwargs: None)

def test_path_injection_denied():
    expected = ExpectedPayment("ORDER/../../bad", 100, "USD", "MERCHANT_SYNTH")
    with pytest.raises(EvidenceError):
        verify_sandbox_capture(expected, client_id="fake", client_secret="fake",
            transport=lambda *args, **kwargs: {"access_token": "fake"})
