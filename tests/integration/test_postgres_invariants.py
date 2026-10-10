"""Real PostgreSQL integration tests. Require TEST_DATABASE_URL to point to an empty disposable DB.

Tests run only when psycopg and TEST_DATABASE_URL are provided. CI postgres job supplies both.
"""
import os
from pathlib import Path
import uuid
from concurrent.futures import ThreadPoolExecutor
import pytest

psycopg = pytest.importorskip("psycopg")
URL = os.environ.get("TEST_DATABASE_URL")
if not URL:
    pytest.skip("TEST_DATABASE_URL not set", allow_module_level=True)

ROOT = Path(__file__).resolve().parents[2]
MIGRATIONS = [ROOT / "db/migrations" / f for f in
              ("001_core.sql","002_transactional_ledger.sql","003_payment_ledger_invariants.sql")]

@pytest.fixture(scope="module", autouse=True)
def schema():
    with psycopg.connect(URL, autocommit=True) as conn:
        for path in MIGRATIONS:
            conn.execute(path.read_text())
    yield

def ids():
    return tuple(str(uuid.uuid4()) for _ in range(4))

def seed():
    partner,customer,order,entry=ids()
    with psycopg.connect(URL) as conn:
        conn.execute("INSERT INTO partners(id,partner_type,status) VALUES (%s,'AGENT','ACTIVE')",(partner,))
        conn.execute("INSERT INTO customers(id) VALUES (%s)",(customer,))
        conn.execute("INSERT INTO orders(id,customer_id,eligible_net_sen,status) VALUES (%s,%s,1200,'CAPTURED')",(order,customer))
    return partner,customer,order,entry

def test_commission_rows_append_only():
    partner,_,order,entry=seed()
    with psycopg.connect(URL) as conn:
        conn.execute("INSERT INTO commission_entries(id,order_id,partner_id,entry_type,amount_sen,business_key,eligible_at) VALUES (%s,%s,%s,'ORIGINAL',36,%s,now())",
                     (entry,order,partner,f"{order}:capture:ORIGINAL"))
    with pytest.raises(psycopg.errors.RaiseException):
        with psycopg.connect(URL) as conn:
            conn.execute("UPDATE commission_entries SET amount_sen=99 WHERE id=%s",(entry,))

def test_capture_duplicate_business_key_rejected():
    partner,_,order,entry=seed()
    with psycopg.connect(URL) as conn:
        conn.execute("INSERT INTO commission_entries(id,order_id,partner_id,entry_type,amount_sen,business_key,eligible_at) VALUES (%s,%s,%s,'ORIGINAL',36,%s,now())",
                     (entry,order,partner,f"{order}:capture:ORIGINAL"))
    with pytest.raises(psycopg.errors.UniqueViolation):
        with psycopg.connect(URL) as conn:
            conn.execute("INSERT INTO commission_entries(id,order_id,partner_id,entry_type,amount_sen,business_key,eligible_at) VALUES (%s,%s,%s,'ORIGINAL',36,%s,now())",
                         (str(uuid.uuid4()),order,partner,f"{order}:capture:ORIGINAL:second"))

def test_concurrent_payment_event_idempotency():
    _,_,order,_=seed()
    event=f"event-{uuid.uuid4()}"
    def insert(_):
        with psycopg.connect(URL) as conn:
            row=conn.execute("""INSERT INTO processed_payment_events(provider,provider_event_id,order_id,payload_hash)
                VALUES ('sandbox',%s,%s,%s) ON CONFLICT DO NOTHING RETURNING provider_event_id""",
                (event,order,"a"*64)).fetchone()
            return bool(row)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results=list(pool.map(insert,range(2)))
    assert sorted(results)==[False,True]

def test_payment_events_append_only():
    _,_,order,_=seed()
    event=f"event-{uuid.uuid4()}"
    with psycopg.connect(URL) as conn:
        conn.execute("INSERT INTO processed_payment_events(provider,provider_event_id,order_id,payload_hash) VALUES ('sandbox',%s,%s,%s)",
                     (event,order,"a"*64))
    with pytest.raises(psycopg.errors.RaiseException):
        with psycopg.connect(URL) as conn:
            conn.execute("DELETE FROM processed_payment_events WHERE provider='sandbox' AND provider_event_id=%s",(event,))

def test_refund_cannot_exceed_capture():
    _,_,order,_=seed()
    with pytest.raises(psycopg.errors.CheckViolation):
        with psycopg.connect(URL) as conn:
            conn.execute("INSERT INTO order_commission_state(order_id,captured_eligible_sen,cumulative_refunded_sen) VALUES (%s,1200,1201)",(order,))

def test_settlement_lock_unique_per_order():
    _,_,order,_=seed()
    a,b=str(uuid.uuid4()),str(uuid.uuid4())
    with psycopg.connect(URL) as conn:
        conn.execute("INSERT INTO settlement_batches(id,status) VALUES (%s,'DRAFT'),(%s,'DRAFT')",(a,b))
        conn.execute("INSERT INTO settlement_locks(order_id,batch_id) VALUES (%s,%s)",(order,a))
    with pytest.raises(psycopg.errors.UniqueViolation):
        with psycopg.connect(URL) as conn:
            conn.execute("INSERT INTO settlement_locks(order_id,batch_id) VALUES (%s,%s)",(order,b))
