"""Proof: failed commission posting cannot commit provider capture mapping."""
from datetime import datetime,timezone
from uuid import uuid4
import os
import pytest
psycopg=pytest.importorskip("psycopg")
URL=os.getenv("TEST_DATABASE_URL")
if not URL:
    pytest.skip("disposable PostgreSQL required",allow_module_level=True)
from canicommerce.provider_mapping import register_mapping,capture_verified
from canicommerce.payment_boundary import VerifiedCapture
from canicommerce.postgres_repository import FinancialConflict

def test_failed_commission_posting_rolls_back_capture_reservation():
    customer,order=[str(uuid4()) for _ in range(2)]
    provider_order="PAYPAL-"+str(uuid4())
    capture_id="CAP-"+str(uuid4())
    with psycopg.connect(URL) as conn:
        conn.execute("INSERT INTO customers(id) VALUES (%s)",(customer,))
        conn.execute("INSERT INTO orders(id,customer_id,eligible_net_sen,status) VALUES (%s,%s,1200,'PENDING')",(order,customer))
    register_mapping(URL,local_order_id=order,provider_order_id=provider_order,
                     expected_merchant_id="M-TEST",expected_gross_sen=1200)
    capture=VerifiedCapture("paypal-sandbox",str(uuid4()),provider_order,
                            capture_id,"MYR",1200,1200,datetime.now(timezone.utc),"f"*64)
    # Force an error inside repository.capture AFTER provider_capture_mappings INSERT
    # by creating a conflicting order_commission_state row.
    with psycopg.connect(URL) as conn:
        conn.execute("INSERT INTO order_commission_state(order_id,captured_eligible_sen) VALUES (%s,1200)",(order,))
    with pytest.raises(psycopg.errors.UniqueViolation):
        capture_verified(URL,capture=capture,local_order_id=order,customer_id=customer)
    with psycopg.connect(URL) as conn:
        assert conn.execute(
            "SELECT count(*) FROM provider_capture_mappings WHERE provider_capture_id=%s",(capture_id,)).fetchone()[0]==0
        assert conn.execute(
            "SELECT count(*) FROM processed_payment_events WHERE provider_event_id=%s",
            (capture.provider_event_id,)).fetchone()[0]==0
        assert conn.execute("SELECT status FROM orders WHERE id=%s",(order,)).fetchone()[0]=="PENDING"
