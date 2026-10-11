from datetime import datetime,timedelta,timezone
from uuid import uuid4
import os
import pytest
psycopg=pytest.importorskip("psycopg")
URL=os.getenv("TEST_DATABASE_URL")
if not URL:
    pytest.skip("requires disposable PostgreSQL",allow_module_level=True)
from canicommerce.postgres_repository import PostgresCommissionRepository
from canicommerce.settlement_approval import approve_batch
from canicommerce.recovery import record_post_approval_refund,RecoveryConflict

NOW=datetime(2026,10,10,tzinfo=timezone.utc)
H="d"*64

def seeded_approved_order():
    customer,agent,shop,order,batch=[str(uuid4()) for _ in range(5)]
    with psycopg.connect(URL) as conn:
        conn.execute("INSERT INTO customers(id) VALUES (%s)",(customer,))
        conn.execute("INSERT INTO partners(id,partner_type,status) VALUES (%s,'AGENT','ACTIVE'),(%s,'SHOP','ACTIVE')",(agent,shop))
        conn.execute("INSERT INTO customer_attributions(id,customer_id,original_agent_id,effective_at) VALUES (%s,%s,%s,%s)",
                     (str(uuid4()),customer,agent,NOW))
        conn.execute("INSERT INTO orders(id,customer_id,selling_partner_id,eligible_net_sen,status) VALUES (%s,%s,%s,1200,'PENDING')",
                     (order,customer,shop))
        conn.execute("INSERT INTO settlement_batches(id,status) VALUES (%s,'DRAFT')",(batch,))
    repo=PostgresCommissionRepository(URL)
    repo.capture(order_id=order,provider="sandbox",event_id=str(uuid4()),payload_hash=H,
                 customer_id=customer,eligible_sen=1200,captured_at=NOW)
    assert repo.claim_settlement(order_id=order,batch_id=batch,as_of=NOW+timedelta(days=29))
    approve_batch(URL,batch,"test-operator",NOW+timedelta(days=29))
    return order,batch

def test_approved_refund_creates_append_only_recovery():
    order,_=seeded_approved_order()
    event=str(uuid4())
    args=dict(order_id=order,provider="sandbox",event_id=event,payload_hash=H,
              cumulative_refunded_sen=600,occurred_at=NOW+timedelta(days=30))
    result=record_post_approval_refund(URL,**args)
    assert result["new_recovery_sen"]==60
    assert result["obligations"]==2
    assert record_post_approval_refund(URL,**args)["duplicate"] is True
    with psycopg.connect(URL) as conn:
        assert conn.execute("SELECT sum(amount_sen) FROM recovery_obligations WHERE order_id=%s",(order,)).fetchone()[0]==60
        assert conn.execute("SELECT sum(amount_sen) FROM commission_entries WHERE order_id=%s",(order,)).fetchone()[0]==120
        with pytest.raises(psycopg.errors.RaiseException):
            conn.execute("DELETE FROM recovery_obligations WHERE order_id=%s",(order,))

def test_incremental_refund_only_adds_difference():
    order,_=seeded_approved_order()
    for cumulative in (600,1200):
        record_post_approval_refund(URL,order_id=order,provider="sandbox",event_id=str(uuid4()),
                                    payload_hash=H,cumulative_refunded_sen=cumulative,
                                    occurred_at=NOW+timedelta(days=30))
    with psycopg.connect(URL) as conn:
        assert conn.execute("SELECT sum(amount_sen) FROM recovery_obligations WHERE order_id=%s",(order,)).fetchone()[0]==120

def test_reject_refund_above_capture():
    order,_=seeded_approved_order()
    with pytest.raises(RecoveryConflict):
        record_post_approval_refund(URL,order_id=order,provider="sandbox",event_id=str(uuid4()),
                                    payload_hash=H,cumulative_refunded_sen=1201,
                                    occurred_at=NOW+timedelta(days=30))
