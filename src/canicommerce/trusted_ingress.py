"""Trusted entrypoint for PayPal Sandbox capture notifications.

No HTTP route, no live payment or payout. This boundary constructs its own
adapter from server-side credentials; callers cannot inject verification flags,
VerifiedCapture objects, or a fake adapter into this entrypoint.
"""
from canicommerce.paypal_transport import adapter_from_environment
from canicommerce.webhook_processor import process_paypal_capture_webhook

def process_trusted_paypal_sandbox_webhook(dsn: str, *, headers: dict,
                                          raw_body: bytes) -> bool:
    """Process untrusted bytes using server-owned PayPal verification.

    Credentials are read at invocation time, never from webhook fields.
    Only enable this in an authenticated, rate-limited, HTTPS server runtime.
    """
    adapter=adapter_from_environment()
    return process_paypal_capture_webhook(
        dsn,adapter=adapter,headers=headers,raw_body=raw_body)
