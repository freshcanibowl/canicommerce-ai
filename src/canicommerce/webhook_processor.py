"""Trusted server-side webhook orchestration (no public HTTP endpoint).

Caller must supply a real PayPalSandboxAdapter with server credentials and
verified HTTPS transport. Never accept local order/customer IDs from webhook.
"""
import json
import psycopg
from canicommerce.provider_mapping import capture_verified

class WebhookRoutingError(ValueError):
    pass

def process_paypal_capture_webhook(dsn: str, *, adapter, headers: dict,
                                  raw_body: bytes) -> bool:
    if not isinstance(raw_body,bytes) or not 0<len(raw_body)<=262144:
        raise WebhookRoutingError("invalid body")
    try:
        event=json.loads(raw_body)
    except (ValueError,UnicodeDecodeError) as exc:
        raise WebhookRoutingError("invalid JSON") from exc
    if not isinstance(event,dict) or event.get("event_type")!="PAYMENT.CAPTURE.COMPLETED":
        raise WebhookRoutingError("unexpected event")
    resource=event.get("resource")
    if not isinstance(resource,dict) or not isinstance(resource.get("id"),str):
        raise WebhookRoutingError("missing capture ID")
    capture_id=resource["id"]
    if not capture_id or len(capture_id)>128 or not capture_id.isascii() or not all(c.isalnum() or c in "-_" for c in capture_id):
        raise WebhookRoutingError("invalid capture ID")
    # The provider order ID in the webhook is an untrusted routing hint only.
    supplementary=resource.get("supplementary_data")
    related=supplementary.get("related_ids") if isinstance(supplementary,dict) else None
    provider_order_id=related.get("order_id") if isinstance(related,dict) else None
    if (not isinstance(provider_order_id,str) or not provider_order_id
            or len(provider_order_id)>128 or not provider_order_id.isascii()
            or not all(c.isalnum() or c in "-_" for c in provider_order_id)):
        raise WebhookRoutingError("invalid provider order routing hint")
    with psycopg.connect(dsn) as conn:
        row=conn.execute(
            """SELECT m.local_order_id,m.expected_merchant_id,m.expected_gross_sen,
                      o.customer_id,o.eligible_net_sen
               FROM provider_order_mappings m JOIN orders o ON o.id=m.local_order_id
               WHERE m.provider='paypal-sandbox' AND m.provider_order_id=%s""",
            (provider_order_id,)).fetchone()
    if row is None:
        raise WebhookRoutingError("unknown provider order")
    local_order_id,merchant,gross_sen,customer_id,eligible_net_sen=row
    verified=adapter.verify_capture(
        headers=headers,raw_body=raw_body,expected_order_id=provider_order_id,
        expected_capture_id=capture_id,expected_gross_sen=gross_sen,
        eligible_net_sen=eligible_net_sen,expected_merchant_id=merchant)
    return capture_verified(
        dsn,capture=verified,local_order_id=str(local_order_id),
        customer_id=str(customer_id))
