"""Capture identity replay safety under real PostgreSQL."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timezone
from uuid import uuid4
import os
import pytest
psycopg=pytest.importorskip("psycopg")
URL=os.getenv("TEST_DATABASE_URL")
if not URL:
    pytest.skip("requires disposable PostgreSQL",allow_module_level=True)
from canicommerce.provider_mapping import register_mapping,capture_verified,ProviderMappingError
from canicommerce.payment_boundary import VerifiedCapture
from canicommerce.postgres_repository import FinancialConflict

NOW=datetime(2026,10,11,tzinfo=timezone.utc)

def seed():
    customer,agent,seller,order=[str(uuid4()) for _ in range(4)]
    provider_order="PAYPAL-"+str(uuid4())
    with psycopg.connect(URL) as conn:
        conn.execute("INSERT INTO customers(id) VALUES (%s)",(customer,))
        conn.execute("INSERT INTO partners(id,partner_type,status) VALUES (%s,'AGENT','ACTIVE'),(%s,'SHOP','ACTIVE')",(agent,seller))
        conn.execute("INSERT INTO customer_attributions(id,customer_id,original_agent_id,effective_at) VALUES (%s,%s,%s,%s)",
                     (str(uuid4()),customer,agent,NOW))
        conn.execute("INSERT INTO orders(id,customer_id,selling_partner_id,eligible_net_sen,status) VALUES (%s,%s,%s,1200,'PENDING')",
                     (order,customer,seller))
    register_mapping(URL,local_order_id=order,provider_order_id=provider_order,
                     expected_merchant_id="M-TEST",expected_gross_sen=1200)
    cap=VerifiedCapture("paypal-sandbox",str(uuid4()),provider_order,
                        "CAP-"+str(uuid4()),"MYR",1200,1200,NOW,"a"*64)
    return customer,order,cap

def test_concurrent_exact_replay_awards_once():
    customer,order,cap=seed()
    def call(_):
        return capture_verified(URL,capture=cap,local_order_id=order,customer_id=customer)
    with ThreadPoolExecutor(max_workers=2) as pool:
        result=list(pool.map(call,range(2)))
    assert sorted(result)==[False,True]
    with psycopg.connect(URL) as conn:
        assert conn.execute("SELECT count(*) FROM provider_capture_mappings WHERE local_order_id=%s",(order,)).fetchone()[0]==1
        assert conn.execute("SELECT count(*) FROM processed_payment_events WHERE order_id=%s",(order,)).fetchone()[0]==1
        assert conn.execute("SELECT sum(amount_sen) FROM commission_entries WHERE order_id=%s",(order,)).fetchone()[0]==120

def test_second_capture_id_cannot_reuse_same_local_order():
    customer,order,cap=seed()
    assert capture_verified(URL,capture=cap,local_order_id=order,customer_id=customer)
    changed=VerifiedCapture(cap.provider,str(uuid4()),cap.order_id,"CAP-"+str(uuid4()),
                            cap.currency,cap.gross_sen,cap.eligible_net_sen,NOW,"b"*64)
    with pytest.raises(ProviderMappingError,match="second capture"):
        capture_verified(URL,capture=changed,local_order_id=order,customer_id=customer)

def test_same_capture_id_different_webhook_event_not_double_awarded():
    customer,order,cap=seed()
    assert capture_verified(URL,capture=cap,local_order_id=order,customer_id=customer)
    another=VerifiedCapture(cap.provider,str(uuid4()),cap.order_id,cap.provider_capture_id,
                            cap.currency,cap.gross_sen,cap.eligible_net_sen,NOW,"b"*64)
    with pytest.raises(FinancialConflict,match="second capture"):
        capture_verified(URL,capture=another,local_order_id=order,customer_id=customer)
    with psycopg.connect(URL) as conn:
        assert conn.execute("SELECT count(*) FROM processed_payment_events WHERE order_id=%s",(order,)).fetchone()[0]==1
