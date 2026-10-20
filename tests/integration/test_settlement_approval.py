from datetime import datetime,timedelta,timezone
from uuid import uuid4
import os
import pytest
psycopg=pytest.importorskip("psycopg")
URL=os.getenv("TEST_DATABASE_URL")
if not URL:
    pytest.skip("requires disposable PostgreSQL",allow_module_level=True)
from canicommerce.postgres_repository import PostgresCommissionRepository,FinancialConflict
from canicommerce.settlement_approval import approve_batch,SettlementApprovalError
NOW=datetime(2026,10,10,tzinfo=timezone.utc)
HASH="c"*64

def setup():
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
    repo.capture(order_id=order,provider="sandbox",event_id=str(uuid4()),payload_hash=HASH,
                 customer_id=customer,eligible_sen=1200,captured_at=NOW)
    assert repo.claim_settlement(order_id=order,batch_id=batch,as_of=NOW+timedelta(days=29))
    return repo,order,batch

def test_approve_valid_claim():
    _,_,batch=setup()
    result=approve_batch(URL,batch,"operator-test",NOW+timedelta(days=29))
    assert result["total_sen"]==120
    with psycopg.connect(URL) as conn:
        assert conn.execute("SELECT status FROM settlement_batches WHERE id=%s",(batch,)).fetchone()[0]=="APPROVED"

def test_refund_after_draft_blocks_stale_approval():
    repo,order,batch=setup()
    repo.refund(order_id=order,provider="sandbox",event_id=str(uuid4()),payload_hash=HASH,
                cumulative_refunded_sen=600,occurred_at=NOW+timedelta(days=28))
    with pytest.raises(SettlementApprovalError,match="stale"):
        approve_batch(URL,batch,"operator-test",NOW+timedelta(days=29))
    with psycopg.connect(URL) as conn:
        assert conn.execute("SELECT status FROM settlement_batches WHERE id=%s",(batch,)).fetchone()[0]=="DRAFT"

def test_refund_after_approval_requires_recovery():
    repo,order,batch=setup()
    approve_batch(URL,batch,"operator-test",NOW+timedelta(days=29))
    with pytest.raises(FinancialConflict,match="recovery"):
        repo.refund(order_id=order,provider="sandbox",event_id=str(uuid4()),payload_hash=HASH,
                    cumulative_refunded_sen=600,occurred_at=NOW+timedelta(days=30))

def test_approval_requires_operator():
    _,_,batch=setup()
    with pytest.raises(SettlementApprovalError,match="operator"):
        approve_batch(URL,batch,"",NOW+timedelta(days=29))
