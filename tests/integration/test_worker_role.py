"""Privilege matrix in disposable PostgreSQL CI only."""
import os
from pathlib import Path
import psycopg
import pytest

@pytest.fixture
def dsn():
    value=os.environ.get("TEST_DATABASE_URL")
    if not value:
        pytest.skip("requires disposable TEST_DATABASE_URL")
    return value

@pytest.fixture
def worker(dsn):
    root=Path(__file__).resolve().parents[2]
    script=(root/"db"/"security"/"002_worker_role.sql").read_text()
    with psycopg.connect(dsn) as conn:
        conn.execute(script)
    return "canicommerce_worker"

def privilege(conn,role,table,permission):
    return conn.execute(
        "SELECT has_table_privilege(%s,%s,%s)",
        (role,"public."+table,permission)).fetchone()[0]

def test_worker_allowed_capture_permissions(dsn,worker):
    with psycopg.connect(dsn) as conn:
        assert privilege(conn,worker,"orders","SELECT")
        assert privilege(conn,worker,"orders","UPDATE")
        for table in ("provider_capture_mappings","processed_payment_events",
                      "order_commission_state","commission_entries"):
            assert privilege(conn,worker,table,"SELECT")
            assert privilege(conn,worker,table,"INSERT")

def test_worker_cannot_control_settlement_or_attribution(dsn,worker):
    with psycopg.connect(dsn) as conn:
        for table in ("settlement_batches","settlement_items","recovery_obligations",
                      "audit_events","customer_attributions","provider_order_mappings"):
            for permission in ("INSERT","UPDATE","DELETE"):
                assert not privilege(conn,worker,table,permission),(table,permission)
        assert not privilege(conn,worker,"orders","DELETE")
        assert not privilege(conn,worker,"commission_entries","UPDATE")
        assert not privilege(conn,worker,"commission_entries","DELETE")

def test_worker_cannot_approve_settlement_by_sql(dsn,worker):
    with psycopg.connect(dsn) as conn:
        with conn.transaction():
            conn.execute("SET LOCAL ROLE canicommerce_worker")
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                conn.execute("UPDATE public.settlement_batches SET status='APPROVED' WHERE false")


def test_worker_cannot_change_order_amount_or_identity(dsn,worker):
    with psycopg.connect(dsn) as conn:
        for column in ('eligible_net_sen','customer_id','selling_partner_id'):
            assert conn.execute(
                'SELECT has_column_privilege(%s,%s,%s,%s)',
                (worker,'public.orders',column,'UPDATE')).fetchone()[0] is False
        assert conn.execute(
            'SELECT has_column_privilege(%s,%s,%s,%s)',
            (worker,'public.orders','status','UPDATE')).fetchone()[0] is True


def test_worker_cannot_mutate_referral_attribution_by_sql(dsn,worker):
    with psycopg.connect(dsn) as conn:
        with conn.transaction():
            conn.execute('SET LOCAL ROLE canicommerce_worker')
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                conn.execute('UPDATE public.customer_attributions SET corrected_at=now() WHERE false')
