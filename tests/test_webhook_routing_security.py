import json
import pytest
from canicommerce.webhook_processor import process_paypal_capture_webhook,WebhookRoutingError

@pytest.mark.parametrize("supplementary",[
    None,[],123,"invalid",{},{"related_ids":None},
    {"related_ids":[]},{"related_ids":"not a dict"},
    {"related_ids":{"order_id":[]}},
    {"related_ids":{"order_id":"a"*129}},
    {"related_ids":{"order_id":"order/../../other"}},
])
def test_malformed_routing_rejected_before_database(supplementary):
    body=json.dumps({"event_type":"PAYMENT.CAPTURE.COMPLETED",
                     "resource":{"id":"CAP-123","supplementary_data":supplementary}}).encode()
    with pytest.raises(WebhookRoutingError):
        process_paypal_capture_webhook("postgresql://invalid",adapter=None,
                                      headers={},raw_body=body)

@pytest.mark.parametrize("resource",[
    None,[],{"id":None},{"id":"a"*129},{"id":"CAP/../BAD"},
])
def test_malformed_capture_rejected_before_database(resource):
    body=json.dumps({"event_type":"PAYMENT.CAPTURE.COMPLETED","resource":resource}).encode()
    with pytest.raises(WebhookRoutingError):
        process_paypal_capture_webhook("postgresql://invalid",adapter=None,
                                      headers={},raw_body=body)
