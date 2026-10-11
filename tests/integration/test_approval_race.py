"""Concurrent approval versus refund, disposable PostgreSQL only."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timedelta,timezone
from uuid import uuid4
import os
import pytest
psycopg=pytest.importorskip("psycopg")
URL=os.getenv("TEST_DATABASE_URL")
if not URL:
    pytest.skip("requires disposable TEST_DATABASE_URL",allow_module_level=True)
from canicommerce.postgres_repository import PostgresCommissionRepository,FinancialConflict
from canicommerce.settlement_approval import approve_batch,SettlementApprovalError
NOW=datetime(2026,10,10,tzinfo=timezone.utc)
H="e"*64

def test_refund_racing_approval_never_approves_stale_amount():
    customer,agent,seller,order,batch=[str(uuid4()) for _ in range(5)]
    with psycopg.connect(URL) as conn:
        conn.execute("INSERT INTO customers(id) VALUES (%s)",(customer,))
        conn.execute("INSERT INTO partners(id,partner_type,status) VALUES (%s,'AGENT','ACTIVE'),(%s,'SHOP','ACTIVE')",(agent,seller))
        conn.execute("INSERT INTO customer_attributions(id,customer_id,original_agent_id,effective_at) VALUES (%s,%s,%s,%s)",
                     (str(uuid4()),customer,agent,NOW))
        conn.execute("INSERT INTO orders(id,customer_id,selling_partner_id,eligible_net_sen,status) VALUES (%s,%s,%s,1200,'PENDING')",
                     (order,customer,seller))
        conn.execute("INSERT INTO settlement_batches(id,status) VALUES (%s,'DRAFT')",(batch,))
    repo=PostgresCommissionRepository(URL)
    repo.capture(order_id=order,provider="sandbox",event_id=str(uuid4()),payload_hash=H,
                 customer_id=customer,eligible_sen=1200,captured_at=NOW)
    assert repo.claim_settlement(order_id=order,batch_id=batch,as_of=NOW+timedelta(days=29))
    def refund():
        try:
            return ("refund",repo.refund(order_id=order,provider="sandbox",event_id=str(uuid4()),
                      payload_hash=H,cumulative_refunded_sen=600,occurred_at=NOW+timedelta(days=30)))
        except (FinancialConflict,psycopg.errors.SerializationFailure):
            return ("refund_rejected",False)
    def approve():
        try:
            return ("approved",approve_batch(URL,batch,"operator-test",NOW+timedelta(days=30)))
        except (SettlementApprovalError,psycopg.errors.SerializationFailure):
            return ("approval_rejected",False)
    with ThreadPoolExecutor(max_workers=2) as pool:
        a=pool.submit(refund)
        b=pool.submit(approve)
        results=(a.result(),b.result())
    with psycopg.connect(URL) as conn:
        status=conn.execute("SELECT status FROM settlement_batches WHERE id=%s",(batch,)).fetchone()[0]
        refunded=conn.execute("SELECT cumulative_refunded_sen FROM order_commission_state WHERE order_id=%s",(order,)).fetchone()[0]
        if status=="APPROVED":
            assert refunded==0, "approved amount must not be stale after refund"
        if refunded==600:
            assert status=="DRAFT", "refund must invalidate old approval"
    assert len(results)==2
