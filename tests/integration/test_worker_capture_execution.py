"""Exercise actual ledger posting with SET ROLE in disposable PostgreSQL CI.

Synthetic test transactions only; never deploy this test as a payment ingress.
"""
import os
from datetime import datetime,timezone
from uuid import uuid4
import pytest
import psycopg
from canicommerce.postgres_repository import PostgresCommissionRepository, FinancialConflict

@pytest.fixture
def dsn():
    value=os.environ.get("TEST_DATABASE_URL")
    if not value: pytest.skip("disposable PostgreSQL required")
    return value

def test_real_capture_under_restricted_worker_role(dsn):
    customer,order,agent,seller=[str(uuid4()) for _ in range(4)]
    now=datetime.now(timezone.utc)
    with psycopg.connect(dsn) as conn:
        conn.execute("INSERT INTO customers(id) VALUES (%s)",(customer,))
        conn.execute("INSERT INTO partners(id,partner_type,status) VALUES (%s,'AGENT','ACTIVE'),(%s,'SHOP','ACTIVE')",(agent,seller))
        conn.execute("INSERT INTO customer_attributions(id,customer_id,original_agent_id,effective_at) VALUES (%s,%s,%s,%s)",
                     (str(uuid4()),customer,agent,now))
        conn.execute("INSERT INTO orders(id,customer_id,selling_partner_id,eligible_net_sen,status) VALUES (%s,%s,%s,1200,'PENDING')",
                     (order,customer,seller))
    # Test role is provisioned by test_worker_role.py; provision independently to avoid test-order dependency.
    from pathlib import Path
    sql=(Path(__file__).resolve().parents[2]/"db"/"security"/"002_worker_role.sql").read_text()
    with psycopg.connect(dsn) as conn:
        conn.execute(sql)
    event="restricted-"+str(uuid4())
    with psycopg.connect(dsn) as conn:
        with conn.transaction():
            conn.execute("SET LOCAL ROLE canicommerce_worker")
            repo=PostgresCommissionRepository(dsn)
            assert repo.capture(order_id=order,provider="paypal-sandbox",event_id=event,
                                payload_hash="b"*64,customer_id=customer,eligible_sen=1200,
                                captured_at=now,connection=conn) is True
    with psycopg.connect(dsn) as conn:
        with conn.transaction():
            conn.execute("SET LOCAL ROLE canicommerce_worker")
            assert PostgresCommissionRepository(dsn).capture(
                order_id=order,provider="paypal-sandbox",event_id=event,
                payload_hash="b"*64,customer_id=customer,eligible_sen=1200,
                captured_at=now,connection=conn) is False
    # Event replay with the same provider ID but a different payload is an error.
    with psycopg.connect(dsn) as conn:
        with conn.transaction():
            conn.execute("SET LOCAL ROLE canicommerce_worker")
            with pytest.raises(FinancialConflict, match="conflicting payload"):
                PostgresCommissionRepository(dsn).capture(
                    order_id=order,provider="paypal-sandbox",event_id=event,
                    payload_hash="d"*64,customer_id=customer,eligible_sen=1200,
                    captured_at=now,connection=conn)
    # A distinct capture event cannot award commission twice.
    with psycopg.connect(dsn) as conn:
        with conn.transaction():
            conn.execute("SET LOCAL ROLE canicommerce_worker")
            with pytest.raises(FinancialConflict, match="second capture"):
                PostgresCommissionRepository(dsn).capture(
                    order_id=order,provider="paypal-sandbox",
                    event_id="different-"+str(uuid4()),payload_hash="c"*64,
                    customer_id=customer,eligible_sen=1200,
                    captured_at=now,connection=conn)
    with psycopg.connect(dsn) as conn:
        assert conn.execute("SELECT status FROM orders WHERE id=%s",(order,)).fetchone()[0]=="CAPTURED"
        rows=conn.execute("SELECT entry_type,amount_sen FROM commission_entries WHERE order_id=%s ORDER BY entry_type",(order,)).fetchall()
        assert rows==[("ORIGINAL",36),("SELLER",84)]
        assert conn.execute("SELECT count(*) FROM processed_payment_events WHERE provider_event_id=%s",(event,)).fetchone()[0]==1
        assert conn.execute("SELECT count(*) FROM commission_entries WHERE order_id=%s",(order,)).fetchone()[0]==2
