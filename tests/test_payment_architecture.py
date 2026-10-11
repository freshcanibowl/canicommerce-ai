"""Architectural regression checks; not a substitute for deployment review."""
import inspect
from pathlib import Path

from canicommerce import trusted_ingress
from canicommerce import paypal_transport

def test_trusted_ingress_does_not_accept_unverified_capture_or_adapter():
    sig=inspect.signature(trusted_ingress.process_trusted_paypal_sandbox_webhook)
    assert set(sig.parameters)=={"dsn","headers","raw_body"}

def test_transport_base_is_sandbox_only():
    assert paypal_transport.BASE=="https://api-m.sandbox.paypal.com"

def test_trusted_ingress_calls_server_owned_adapter():
    source=inspect.getsource(trusted_ingress.process_trusted_paypal_sandbox_webhook)
    assert "adapter_from_environment()" in source
    assert "process_paypal_capture_webhook(" in source

def test_security_release_gates_are_explicit():
    document=Path(__file__).resolve().parents[1]/"docs"/"payment-trust-boundary.md"
    text=document.read_text(encoding="utf-8")
    assert "NOT production-ready" in text
    assert "VerifiedCapture" in text
    assert "least privilege" in text
