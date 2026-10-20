import inspect
import pytest
from canicommerce.trusted_ingress import process_trusted_paypal_sandbox_webhook
from canicommerce.paypal_transport import PayPalTransportError

def test_public_trusted_ingress_has_no_adapter_or_capture_injection():
    parameters=inspect.signature(process_trusted_paypal_sandbox_webhook).parameters
    assert set(parameters)=={"dsn","headers","raw_body"}
    assert "adapter" not in parameters
    assert "capture" not in parameters

def test_missing_credentials_fail_closed_before_database(monkeypatch):
    for name in ("PAYPAL_SANDBOX_WEBHOOK_ID","PAYPAL_SANDBOX_CLIENT_ID","PAYPAL_SANDBOX_CLIENT_SECRET"):
        monkeypatch.delenv(name,raising=False)
    with pytest.raises(PayPalTransportError):
        process_trusted_paypal_sandbox_webhook(
            "postgresql://not-used",headers={},raw_body=b"{}")
