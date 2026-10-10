"""Apply schema once to the disposable PostgreSQL test database per test session."""
import os
from pathlib import Path
import pytest

@pytest.fixture(scope="session", autouse=True)
def migrated_test_schema():
    dsn = os.environ.get("TEST_DATABASE_URL")
    if not dsn:
        return
    psycopg = pytest.importorskip("psycopg")
    root = Path(__file__).resolve().parents[2]
    with psycopg.connect(dsn, autocommit=True) as conn:
        for name in ("001_core.sql", "002_transactional_ledger.sql", "003_payment_ledger_invariants.sql"):
            conn.execute((root / "db" / "migrations" / name).read_text())
