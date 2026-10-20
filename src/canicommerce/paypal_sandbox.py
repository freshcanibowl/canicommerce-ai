"""PayPal Sandbox adapter. Network transport is injected for deterministic tests.

Do NOT accept verification booleans from HTTP clients. Signature validation
and capture reconciliation are performed against PayPal's server APIs.
No checkout creation, payout, or production credentials.
"""
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import json
from urllib.parse import urlparse

from canicommerce.payment_boundary import (
    PaymentVerificationError, verified_capture_from_provider,
)

class PayPalSandboxAdapter:
    def __init__(self, *, webhook_id: str, get_access_token, post_json, get_json):
        if not webhook_id:
            raise ValueError("PayPal webhook ID required")
        self.webhook_id = webhook_id
        self.get_access_token = get_access_token
        self.post_json = post_json
        self.get_json = get_json

    def verify_capture(self, *, headers: dict, raw_body: bytes, expected_order_id: str,
                       expected_capture_id: str, expected_gross_sen: int,
                       eligible_net_sen: int, expected_merchant_id: str):
        if not isinstance(raw_body,bytes) or len(raw_body)>262144 or not raw_body:
            raise PaymentVerificationError("invalid webhook body")
        required=("paypal-transmission-id","paypal-transmission-time",
                  "paypal-transmission-sig","paypal-cert-url","paypal-auth-algo")
        h={str(k).lower():v for k,v in headers.items()}
        if any(not h.get(k) for k in required):
            raise PaymentVerificationError("missing PayPal signature headers")
        cert=urlparse(h["paypal-cert-url"])
        if (cert.scheme!="https" or cert.hostname not in ("api-m.sandbox.paypal.com","api.sandbox.paypal.com")
                or cert.port not in (None,443) or cert.username or cert.password or cert.fragment):
            raise PaymentVerificationError("untrusted PayPal certificate URL")
        try:
            event=json.loads(raw_body)
        except (ValueError,UnicodeDecodeError) as exc:
            raise PaymentVerificationError("invalid PayPal JSON") from exc
        if not isinstance(event,dict) or event.get("event_type")!="PAYMENT.CAPTURE.COMPLETED":
            raise PaymentVerificationError("unexpected PayPal event")
        capture=event.get("resource")
        if not isinstance(capture,dict) or capture.get("id")!=expected_capture_id:
            raise PaymentVerificationError("webhook capture mismatch")
        if capture.get("status") not in (None,"COMPLETED"):
            raise PaymentVerificationError("webhook capture not completed")
        token=self.get_access_token()
        if not token:
            raise PaymentVerificationError("missing server-side PayPal token")
        verify=self.post_json(
            "https://api-m.sandbox.paypal.com/v1/notifications/verify-webhook-signature",
            {"auth_algo":h["paypal-auth-algo"],"cert_url":h["paypal-cert-url"],
             "transmission_id":h["paypal-transmission-id"],
             "transmission_sig":h["paypal-transmission-sig"],
             "transmission_time":h["paypal-transmission-time"],
             "webhook_id":self.webhook_id,"webhook_event":event},token)
        if not isinstance(verify,dict) or verify.get("verification_status")!="SUCCESS":
            raise PaymentVerificationError("PayPal signature verification failed")
        detail=self.get_json(
            "https://api-m.sandbox.paypal.com/v2/payments/captures/"+expected_capture_id,token)
        if not isinstance(detail,dict) or detail.get("id")!=expected_capture_id or detail.get("status")!="COMPLETED":
            raise PaymentVerificationError("PayPal capture not completed")
        amount=detail.get("amount") or {}
        if amount.get("currency_code")!="MYR":
            raise PaymentVerificationError("PayPal currency mismatch")
        try:
            decimal=Decimal(str(amount["value"]))
            sen=decimal*100
            if not sen.is_finite() or sen!=sen.to_integral_value():
                raise ValueError("non-sen amount")
            gross_sen=int(sen)
        except (KeyError,InvalidOperation,ValueError,TypeError) as exc:
            raise PaymentVerificationError("invalid PayPal capture amount") from exc
        if gross_sen!=expected_gross_sen:
            raise PaymentVerificationError("PayPal amount mismatch")
        if detail.get("payee",{}).get("merchant_id")!=expected_merchant_id:
            raise PaymentVerificationError("PayPal merchant mismatch")
        # PayPal capture links to its provider order; mapping to local order
        # must be checked against a trusted server-side order association.
        paypal_order_id=(detail.get("supplementary_data") or {}).get("related_ids",{}).get("order_id")
        if not paypal_order_id:
            raise PaymentVerificationError("missing PayPal order association")
        # expected_order_id is the trusted provider order ID in this adapter.
        if paypal_order_id!=expected_order_id:
            raise PaymentVerificationError("PayPal order mismatch")
        event_id=event.get("id")
        if not event_id:
            raise PaymentVerificationError("missing webhook event ID")
        return verified_capture_from_provider(
            provider="paypal-sandbox",event_id=event_id,order_id=expected_order_id,
            capture_id=expected_capture_id,currency="MYR",gross_sen=gross_sen,
            eligible_net_sen=eligible_net_sen,provider_signature_verified=True,
            provider_capture_confirmed=True,provider_order_id=paypal_order_id,
            provider_currency="MYR",provider_gross_sen=gross_sen,
            raw_payload=raw_body,verified_at=datetime.now(timezone.utc))
