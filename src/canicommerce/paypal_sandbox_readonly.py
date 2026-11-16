"""Read-only PayPal Sandbox verification. No capture/refund/payout endpoint exists here.

An authenticated API GET establishes provider response provenance only within
the configured sandbox TLS and OAuth context; merchant ownership must be
checked against independently stored expected merchant identity.
"""
import base64
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any, Callable, Mapping

from .payment_contract import ExpectedPayment, EvidenceError, parse_paypal_capture

BASE = "https://api-m.sandbox.paypal.com"
_ID = re.compile(r"^[A-Za-z0-9_-]{1,128}$")

@dataclass(frozen=True)
class VerifiedCapture:
    capture_id: str
    order_id: str
    merchant_id: str
    amount_minor: int
    currency: str
    evidence_level: str = "PROVIDER_READBACK_SANDBOX"

def _id(value: str) -> str:
    if not isinstance(value, str) or not _ID.fullmatch(value):
        raise EvidenceError("invalid provider ID")
    return value

def _request(method: str, path: str, *, headers: Mapping[str, str], data: bytes | None = None) -> Mapping[str, Any]:
    if method not in ("GET", "POST") or not path.startswith("/") or "//" in path or "?" in path:
        raise EvidenceError("invalid request")
    if method == "POST" and path != "/v1/oauth2/token":
        raise EvidenceError("money-moving POST prohibited")
    request = urllib.request.Request(BASE + path, data=data, headers=dict(headers), method=method)
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            raw = response.read(1_000_001)
            if len(raw) > 1_000_000:
                raise EvidenceError("oversized provider response")
            result = json.loads(raw)
            if not isinstance(result, dict):
                raise EvidenceError("invalid provider JSON")
            return result
    except (urllib.error.URLError, ValueError) as exc:
        # No provider response body, request headers, tokens, or credentials in errors.
        raise EvidenceError("sandbox request failed or response invalid") from None

def _oauth(client_id: str, client_secret: str, transport: Callable[..., Mapping[str, Any]]) -> str:
    if not client_id or not client_secret:
        raise EvidenceError("missing sandbox credentials")
    basic = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
    response = transport("POST", "/v1/oauth2/token",
        headers={"Authorization": "Basic " + basic, "Content-Type": "application/x-www-form-urlencoded"},
        data=b"grant_type=client_credentials")
    token = response.get("access_token")
    if not isinstance(token, str) or not token:
        raise EvidenceError("sandbox OAuth failed")
    return token

def verify_sandbox_capture(expected: ExpectedPayment, *,
                           client_id: str, client_secret: str,
                           transport: Callable[..., Mapping[str, Any]] = _request) -> VerifiedCapture:
    """Never posts a payment action. Only one purchase unit/capture supported (fail closed)."""
    order_id = _id(expected.order_id)
    token = _oauth(client_id, client_secret, transport)
    auth = {"Authorization": "Bearer " + token, "Accept": "application/json"}
    order = transport("GET", "/v2/checkout/orders/" + order_id, headers=auth)
    if order.get("id") != order_id or order.get("status") != "COMPLETED":
        raise EvidenceError("order not completed or identity mismatch")
    units = order.get("purchase_units")
    if not isinstance(units, list) or len(units) != 1 or not isinstance(units[0], dict):
        raise EvidenceError("unsupported purchase unit structure")
    unit = units[0]
    payee = unit.get("payee")
    if not isinstance(payee, dict) or payee.get("merchant_id") != expected.merchant_id:
        raise EvidenceError("merchant ownership not verified")
    payments = unit.get("payments")
    captures = payments.get("captures") if isinstance(payments, dict) else None
    if not isinstance(captures, list) or len(captures) != 1 or not isinstance(captures[0], dict):
        raise EvidenceError("unsupported capture structure")
    capture_id = _id(captures[0].get("id"))
    # Independent capture GET, not just an embedded order object or browser callback.
    capture = transport("GET", "/v2/payments/captures/" + capture_id, headers=auth)
    if capture.get("id") != capture_id or captures[0].get("status") != "COMPLETED":
        raise EvidenceError("capture identity or order status mismatch")
    parsed = parse_paypal_capture(capture, expected,
        authenticated_order_id=order_id, authenticated_merchant_id=payee["merchant_id"])
    # Cross-check order embedded capture amount as a second consistency condition.
    embedded = captures[0].get("amount")
    if not isinstance(embedded, dict) or embedded != capture.get("amount"):
        raise EvidenceError("order/capture amount disagreement")
    return VerifiedCapture(parsed.capture_id, order_id, expected.merchant_id,
                           parsed.amount_minor, parsed.currency)

def verify_from_environment(expected: ExpectedPayment) -> VerifiedCapture:
    if os.environ.get("PAYPAL_MODE") != "sandbox":
        raise EvidenceError("PAYPAL_MODE must be sandbox")
    return verify_sandbox_capture(expected,
        client_id=os.environ.get("PAYPAL_CLIENT_ID", ""),
        client_secret=os.environ.get("PAYPAL_CLIENT_SECRET", ""))
