"""Dedicated disposable CI database only: prove the edge role cannot write ledger."""
from pathlib import Path
import psycopg
import pytest

@pytest.fixture
def edge_role(test_dsn):
    script=(Path(__file__).resolve().parents[2]/"db"/"security"/"001_edge_role.sql").read_text()
    with psycopg.connect(test_dsn) as conn:
        conn.execute(script)
    return "canicommerce_edge"

def test_edge_role_has_no_financial_table_privileges(test_dsn,edge_role):
    protected=[
        "orders","processed_payment_events","provider_order_mappings",
        "provider_capture_mappings","commission_entries","settlement_batches",
        "settlement_items","order_commission_state","recovery_obligations",
    ]
    with psycopg.connect(test_dsn) as conn:
        for table in protected:
            row=conn.execute(
                """SELECT has_table_privilege(%s,%s,%s)""",
                (edge_role,"public."+table,"SELECT,INSERT,UPDATE,DELETE")).fetchone()
            assert row[0] is False,table

def test_edge_role_has_no_schema_usage(test_dsn,edge_role):
    with psycopg.connect(test_dsn) as conn:
        assert conn.execute(
            "SELECT has_schema_privilege(%s,'public','USAGE')",(edge_role,)
        ).fetchone()[0] is False
        assert conn.execute(
            "SELECT has_schema_privilege(%s,'public','CREATE')",(edge_role,)
        ).fetchone()[0] is False
