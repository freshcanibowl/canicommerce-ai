from datetime import datetime,timezone
from uuid import uuid4
import os
import pytest
psycopg=pytest.importorskip("psycopg")
URL=os.getenv("TEST_DATABASE_URL")
if not URL:
    pytest.skip("disposable PostgreSQL required",allow_module_level=True)
from canicommerce.provider_mapping import register_mapping,capture_verified,ProviderMappingError
from canicommerce.payment_boundary import VerifiedCapture

NOW=datetime(2026,10,11,tzinfo=timezone.utc)

def setup():
    customer,agent,shop,order=[str(uuid4()) for _ in range(4)]
    with psycopg.connect(URL) as conn:
        conn.execute("INSERT INTO customers(id) VALUES (%s)",(customer,))
        conn.execute("INSERT INTO partners(id,partner_type,status) VALUES (%s,'AGENT','ACTIVE'),(%s,'SHOP','ACTIVE')",(agent,shop))
        conn.execute("INSERT INTO customer_attributions(id,customer_id,original_agent_id,effective_at) VALUES (%s,%s,%s,%s)",
                     (str(uuid4()),customer,agent,NOW))
        conn.execute("INSERT INTO orders(id,customer_id,selling_partner_id,eligible_net_sen,status) VALUES (%s,%s,%s,1200,'PENDING')",
                     (order,customer,shop))
    provider_order="PAYPAL-"+str(uuid4())
    register_mapping(URL,local_order_id=order,provider_order_id=provider_order,
                     expected_merchant_id="M-TEST",expected_gross_sen=1200)
    capture=VerifiedCapture("paypal-sandbox",str(uuid4()),provider_order,
                             "CAP-"+str(uuid4()),"MYR",1200,1200,NOW,"a"*64)
    return customer,order,capture

def test_verified_capture_posts_commissions_once():
    customer,order,capture=setup()
    assert capture_verified(URL,capture=capture,local_order_id=order,customer_id=customer) is True
    assert capture_verified(URL,capture=capture,local_order_id=order,customer_id=customer) is False
    with psycopg.connect(URL) as conn:
        assert conn.execute("SELECT sum(amount_sen) FROM commission_entries WHERE order_id=%s",(order,)).fetchone()[0]==120

def test_wrong_local_order_rejected():
    customer,order,capture=setup()
    with pytest.raises(ProviderMappingError):
        capture_verified(URL,capture=capture,local_order_id=str(uuid4()),customer_id=customer)

def test_wrong_provider_gross_rejected():
    customer,order,capture=setup()
    changed=VerifiedCapture(capture.provider,capture.provider_event_id,capture.order_id,
                             capture.provider_capture_id,capture.currency,1199,
                             capture.eligible_net_sen,capture.verified_at,capture.payload_hash)
    with pytest.raises(ProviderMappingError):
        capture_verified(URL,capture=changed,local_order_id=order,customer_id=customer)
