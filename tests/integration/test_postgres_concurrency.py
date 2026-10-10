"""Build 1.4 concurrency regression against disposable PostgreSQL.
No production databases or payment gateway credentials.
"""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from uuid import uuid4
import os
import pytest

psycopg = pytest.importorskip("psycopg")
URL = os.getenv("TEST_DATABASE_URL")
if not URL:
    pytest.skip("requires TEST_DATABASE_URL", allow_module_level=True)

from canicommerce.postgres_repository import PostgresCommissionRepository, FinancialConflict

NOW = datetime(2026, 10, 10, tzinfo=timezone.utc)
HASH = "b" * 64

def new_order():
    customer, agent, seller, order = [str(uuid4()) for _ in range(4)]
    with psycopg.connect(URL) as conn:
        conn.execute("INSERT INTO customers(id) VALUES (%s)", (customer,))
        conn.execute(
            "INSERT INTO partners(id,partner_type,status) VALUES (%s,'AGENT','ACTIVE'),(%s,'SHOP','ACTIVE')",
            (agent, seller))
        conn.execute(
            "INSERT INTO customer_attributions(id,customer_id,original_agent_id,effective_at) VALUES (%s,%s,%s,%s)",
            (str(uuid4()), customer, agent, NOW))
        conn.execute(
            "INSERT INTO orders(id,customer_id,selling_partner_id,eligible_net_sen,status) VALUES (%s,%s,%s,1200,'PENDING')",
            (order, customer, seller))
    return customer, order

def capture(customer, order):
    return PostgresCommissionRepository(URL).capture(
        order_id=order, provider="sandbox", event_id=str(uuid4()),
        payload_hash=HASH, customer_id=customer, eligible_sen=1200, captured_at=NOW)

def test_two_distinct_capture_events_cannot_double_award():
    customer, order = new_order()
    def attempt(_):
        try:
            return ("ok", capture(customer, order))
        except (FinancialConflict, psycopg.errors.SerializationFailure) as exc:
            return ("rejected", type(exc).__name__)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(attempt, range(2)))
    assert len([x for x in results if x[0] == "ok" and x[1] is True]) == 1
    with psycopg.connect(URL) as conn:
        rows = conn.execute(
            "SELECT entry_type,amount_sen FROM commission_entries WHERE order_id=%s ORDER BY entry_type",
            (order,)).fetchall()
        assert len(rows) == 2
        assert sorted(amount for _, amount in rows) == [36,84]

def test_refund_and_settlement_claim_are_serialized():
    customer, order = new_order()
    capture(customer, order)
    batch = str(uuid4())
    with psycopg.connect(URL) as conn:
        conn.execute("INSERT INTO settlement_batches(id,status) VALUES (%s,'DRAFT')", (batch,))
    repo = PostgresCommissionRepository(URL)
    def refund():
        try:
            return ("refund", repo.refund(
                order_id=order, provider="sandbox", event_id=str(uuid4()),
                payload_hash=HASH, cumulative_refunded_sen=1200,
                occurred_at=NOW + timedelta(days=28)))
        except (FinancialConflict, psycopg.errors.SerializationFailure) as exc:
            return ("refund_rejected", type(exc).__name__)
    def claim():
        try:
            return ("claim", repo.claim_settlement(
                order_id=order, batch_id=batch, as_of=NOW + timedelta(days=29)))
        except (FinancialConflict, psycopg.errors.SerializationFailure) as exc:
            return ("claim_rejected", type(exc).__name__)
    with ThreadPoolExecutor(max_workers=2) as pool:
        a = pool.submit(refund)
        b = pool.submit(claim)
        results = [a.result(), b.result()]
    with psycopg.connect(URL) as conn:
        refunded = conn.execute(
            "SELECT cumulative_refunded_sen FROM order_commission_state WHERE order_id=%s",
            (order,)).fetchone()[0]
        locks = conn.execute(
            "SELECT count(*) FROM settlement_locks WHERE order_id=%s",
            (order,)).fetchone()[0]
        assert refunded in (0,1200)
        assert locks in (0,1)
        # If a full refund commits before the claim, settlement must not be claimed.
        if refunded == 1200:
            # A claim may have been inserted first, but is still only a DRAFT.
            assert conn.execute(
                """SELECT count(*) FROM settlement_batches b JOIN settlement_locks l
                   ON l.batch_id=b.id WHERE l.order_id=%s AND b.status='PAID'""",
                (order,)).fetchone()[0] == 0
    assert len(results) == 2
