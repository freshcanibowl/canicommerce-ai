"""DB-backed transactional tests in disposable PostgreSQL CI database."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timedelta,timezone
from pathlib import Path
from uuid import uuid4
import os
import pytest
psycopg=pytest.importorskip("psycopg")
if not os.environ.get("TEST_DATABASE_URL"):
    pytest.skip("requires disposable TEST_DATABASE_URL",allow_module_level=True)
from canicommerce.postgres_repository import PostgresCommissionRepository, FinancialConflict
URL=os.environ["TEST_DATABASE_URL"]
NOW=datetime(2026,10,10,tzinfo=timezone.utc)
H="a"*64

@pytest.fixture(scope="module",autouse=True)
def schema():
    root=Path(__file__).resolve().parents[2]
    with psycopg.connect(URL,autocommit=True) as conn:
        for i in ("001_core.sql","002_transactional_ledger.sql","003_payment_ledger_invariants.sql"):
            conn.execute((root/"db"/"migrations"/i).read_text())

def seed():
    customer,agent,shop,order=[str(uuid4()) for _ in range(4)]
    with psycopg.connect(URL) as conn:
        conn.execute("INSERT INTO customers(id) VALUES (%s)",(customer,))
        conn.execute("INSERT INTO partners(id,partner_type,status) VALUES (%s,'AGENT','ACTIVE'),(%s,'SHOP','ACTIVE')",(agent,shop))
        conn.execute("INSERT INTO customer_attributions(id,customer_id,original_agent_id,effective_at) VALUES (%s,%s,%s,%s)",
                     (str(uuid4()),customer,agent,NOW))
        conn.execute("INSERT INTO orders(id,customer_id,selling_partner_id,eligible_net_sen,status) VALUES (%s,%s,%s,1200,'PENDING')",
                     (order,customer,shop))
    return customer,agent,shop,order

def test_atomic_capture_and_refund():
    customer,agent,shop,order=seed()
    repo=PostgresCommissionRepository(URL)
    assert repo.capture(order_id=order,provider="sandbox",event_id=str(uuid4()),payload_hash=H,
                        customer_id=customer,eligible_sen=1200,captured_at=NOW)
    with psycopg.connect(URL) as conn:
        rows=conn.execute("SELECT partner_id,amount_sen FROM commission_entries WHERE order_id=%s ORDER BY amount_sen",(order,)).fetchall()
        assert [(str(x[0]),x[1]) for x in rows]==[(agent,36),(shop,84)]
    assert repo.refund(order_id=order,provider="sandbox",event_id=str(uuid4()),payload_hash=H,
                       cumulative_refunded_sen=600,occurred_at=NOW+timedelta(days=1))
    with psycopg.connect(URL) as conn:
        assert conn.execute("SELECT sum(amount_sen) FROM commission_entries WHERE order_id=%s",(order,)).fetchone()[0]==60

def test_same_event_duplicate_is_noop():
    customer,_,_,order=seed()
    repo=PostgresCommissionRepository(URL)
    event=str(uuid4())
    args=dict(order_id=order,provider="sandbox",event_id=event,payload_hash=H,
              customer_id=customer,eligible_sen=1200,captured_at=NOW)
    assert repo.capture(**args) is True
    assert repo.capture(**args) is False

def test_distinct_capture_event_rejected():
    customer,_,_,order=seed()
    repo=PostgresCommissionRepository(URL)
    args=dict(order_id=order,provider="sandbox",payload_hash=H,
              customer_id=customer,eligible_sen=1200,captured_at=NOW)
    assert repo.capture(event_id=str(uuid4()),**args)
    with pytest.raises(FinancialConflict):
        repo.capture(event_id=str(uuid4()),**args)
    with psycopg.connect(URL) as conn:
        assert conn.execute("SELECT count(*) FROM commission_entries WHERE order_id=%s",(order,)).fetchone()[0]==2

def test_refund_then_settlement_claim():
    customer,_,_,order=seed()
    repo=PostgresCommissionRepository(URL)
    repo.capture(order_id=order,provider="sandbox",event_id=str(uuid4()),payload_hash=H,
                 customer_id=customer,eligible_sen=1200,captured_at=NOW)
    repo.refund(order_id=order,provider="sandbox",event_id=str(uuid4()),payload_hash=H,
                cumulative_refunded_sen=1200,occurred_at=NOW+timedelta(days=1))
    batch=str(uuid4())
    with psycopg.connect(URL) as conn:
        conn.execute("INSERT INTO settlement_batches(id,status) VALUES (%s,'DRAFT')",(batch,))
    assert not repo.claim_settlement(order_id=order,batch_id=batch,as_of=NOW+timedelta(days=29))

def test_claim_blocks_second_claim():
    customer,_,_,order=seed()
    repo=PostgresCommissionRepository(URL)
    repo.capture(order_id=order,provider="sandbox",event_id=str(uuid4()),payload_hash=H,
                 customer_id=customer,eligible_sen=1200,captured_at=NOW)
    batch=str(uuid4())
    with psycopg.connect(URL) as conn:
        conn.execute("INSERT INTO settlement_batches(id,status) VALUES (%s,'DRAFT')",(batch,))
    assert repo.claim_settlement(order_id=order,batch_id=batch,as_of=NOW+timedelta(days=28))
    assert not repo.claim_settlement(order_id=order,batch_id=batch,as_of=NOW+timedelta(days=29))
