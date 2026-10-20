"""PostgreSQL audit journal must reject updates and deletes, even by table owner."""
from uuid import uuid4

import pytest

psycopg = pytest.importorskip("psycopg")


def test_audit_history_is_append_only():
    import os
    dsn = os.environ.get("TEST_DATABASE_URL")
    if not dsn:
        pytest.skip("TEST_DATABASE_URL required")
    event_id = uuid4()
    with psycopg.connect(dsn) as conn:
        conn.execute(
            "INSERT INTO audit_events (id, actor_id, action, entity_type, entity_id, reason) "
            "VALUES (%s, %s, %s, %s, %s, %s)",
            (event_id, "integration-test", "CHECK", "test", str(event_id), "disposable database"),
        )
    for statement in (
        "UPDATE audit_events SET reason = 'changed' WHERE id = %s",
        "DELETE FROM audit_events WHERE id = %s",
    ):
        with psycopg.connect(dsn) as conn:
            with pytest.raises(psycopg.errors.RaiseException, match="immutable"):
                conn.execute(statement, (event_id,))
    with psycopg.connect(dsn) as conn:
        row = conn.execute(
            "SELECT reason FROM audit_events WHERE id = %s", (event_id,)
        ).fetchone()
        assert row == ("disposable database",)
