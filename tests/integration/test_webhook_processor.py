import json
import os
from datetime import datetime,timezone
from uuid import uuid4
import pytest
psycopg=pytest.importorskip("psycopg")
URL=os.getenv("TEST_DATABASE_URL")
if not URL:
    pytest.skip("disposable PostgreSQL required",allow_module_level=True)
from canicommerce.provider_mapping import register_mapping
from canicommerce.webhook_processor import process_paypal_capture_webhook,WebhookRoutingError
from canicommerce.payment_boundary import VerifiedCapture

def test_server_owned_mapping_and_idempotent_webhook():
    customer,order,agent,seller=[str(uuid4()) for _ in range(4)]
    provider_order="PAYPAL-"+str(uuid4())
    capture_id="CAP-"+str(uuid4())
    with psycopg.connect(URL) as conn:
        conn.execute("INSERT INTO customers(id) VALUES (%s)",(customer,))
        conn.execute("INSERT INTO partners(id,partner_type,status) VALUES (%s,'AGENT','ACTIVE'),(%s,'SHOP','ACTIVE')",(agent,seller))
        conn.execute("INSERT INTO customer_attributions(id,customer_id,original_agent_id,effective_at) VALUES (%s,%s,%s,%s)",
                     (str(uuid4()),customer,agent,datetime.now(timezone.utc)))
        conn.execute("INSERT INTO orders(id,customer_id,selling_partner_id,eligible_net_sen,status) VALUES (%s,%s,%s,1200,'PENDING')",
                     (order,customer,seller))
    register_mapping(URL,local_order_id=order,provider_order_id=provider_order,
                     expected_merchant_id="MERCHANT",expected_gross_sen=1500)
    body=json.dumps({"id":"WH-"+str(uuid4()),"event_type":"PAYMENT.CAPTURE.COMPLETED",
                     "resource":{"id":capture_id,"supplementary_data":{"related_ids":{"order_id":provider_order}},
                                 "local_order_id":str(uuid4()),"eligible_net_sen":999999}}).encode()
    class FakeAdapter:
        def verify_capture(self,**kwargs):
            assert kwargs["expected_order_id"]==provider_order
            assert kwargs["expected_gross_sen"]==1500
            assert kwargs["eligible_net_sen"]==1200
            assert kwargs["expected_merchant_id"]=="MERCHANT"
            return VerifiedCapture("paypal-sandbox","WH-EVENT",provider_order,capture_id,
                                   "MYR",1500,1200,datetime.now(timezone.utc),"a"*64)
    adapter=FakeAdapter()
    assert process_paypal_capture_webhook(URL,adapter=adapter,headers={},raw_body=body) is True
    assert process_paypal_capture_webhook(URL,adapter=adapter,headers={},raw_body=body) is False
    with psycopg.connect(URL) as conn:
        assert conn.execute("SELECT sum(amount_sen) FROM commission_entries WHERE order_id=%s",(order,)).fetchone()[0]==120

def test_unknown_provider_order_rejected_before_adapter():
    body=json.dumps({"id":"WH","event_type":"PAYMENT.CAPTURE.COMPLETED",
                     "resource":{"id":"CAP-TEST","supplementary_data":{"related_ids":{"order_id":"UNREGISTERED"}}}}).encode()
    with pytest.raises(WebhookRoutingError,match="unknown provider order"):
        process_paypal_capture_webhook(URL,adapter=None,headers={},raw_body=body)
