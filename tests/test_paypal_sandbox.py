import json
import pytest
from canicommerce.paypal_sandbox import PayPalSandboxAdapter
from canicommerce.payment_boundary import PaymentVerificationError

HEADERS={
 "PAYPAL-TRANSMISSION-ID":"transmission-1",
 "PAYPAL-TRANSMISSION-TIME":"2026-10-11T00:00:00Z",
 "PAYPAL-TRANSMISSION-SIG":"signed",
 "PAYPAL-CERT-URL":"https://api-m.sandbox.paypal.com/certs/cert.pem",
 "PAYPAL-AUTH-ALGO":"SHA256withRSA"
}
BODY=json.dumps({"id":"WH-1","event_type":"PAYMENT.CAPTURE.COMPLETED",
                 "resource":{"id":"CAP-1"}}).encode()

def adapter(signature="SUCCESS",capture_status="COMPLETED",amount="12.00",merchant="M-1",order="P-ORDER-1"):
    return PayPalSandboxAdapter(
        webhook_id="WH-ID",get_access_token=lambda:"test-token",
        post_json=lambda url,payload,token:{"verification_status":signature},
        get_json=lambda url,token:{"id":"CAP-1","status":capture_status,
           "amount":{"currency_code":"MYR","value":amount},
           "payee":{"merchant_id":merchant},
           "supplementary_data":{"related_ids":{"order_id":order}}})

def run(a,headers=None,body=None):
    return a.verify_capture(
        headers=HEADERS if headers is None else headers,
        raw_body=BODY if body is None else body,
        expected_order_id="P-ORDER-1",expected_capture_id="CAP-1",
        expected_gross_sen=1200,eligible_net_sen=1000,expected_merchant_id="M-1")

def test_verified_sandbox_capture():
    assert run(adapter()).eligible_net_sen==1000

@pytest.mark.parametrize("kwargs",[
    {"signature":"FAILURE"},{"capture_status":"PENDING"},{"amount":"12.01"},
    {"amount":"12.001"},{"merchant":"OTHER"},{"order":"OTHER"}
])
def test_reject_provider_mismatch(kwargs):
    with pytest.raises(PaymentVerificationError):
        run(adapter(**kwargs))

def test_reject_untrusted_certificate_host():
    h={**HEADERS,"PAYPAL-CERT-URL":"https://api-m.sandbox.paypal.com.attacker.test/cert"}
    with pytest.raises(PaymentVerificationError):
        run(adapter(),headers=h)

def test_reject_unsigned_webhook():
    with pytest.raises(PaymentVerificationError):
        run(adapter(),headers={})

def test_reject_non_capture_event():
    body=json.dumps({"id":"WH-1","event_type":"PAYMENT.CAPTURE.DENIED",
                     "resource":{"id":"CAP-1"}}).encode()
    with pytest.raises(PaymentVerificationError):
        run(adapter(),body=body)
