"""Fail-closed settlement approval: no payment or payout execution.

Lock the batch, all orders and refund state, then validate *every* item.
Use one SERIALIZABLE transaction to avoid stale approval after refund.
"""
from collections import defaultdict
from psycopg.errors import SerializationFailure
import psycopg

class SettlementApprovalError(ValueError):
    pass

def approve_batch(dsn: str, batch_id: str, approved_by: str, as_of) -> dict:
    if not approved_by:
        raise SettlementApprovalError("operator identity required")
    with psycopg.connect(dsn) as conn:
        with conn.transaction():
            conn.execute("SET TRANSACTION ISOLATION LEVEL SERIALIZABLE")
            batch=conn.execute(
                "SELECT status FROM settlement_batches WHERE id=%s FOR UPDATE",
                (batch_id,)).fetchone()
            if batch is None or batch[0] != "DRAFT":
                raise SettlementApprovalError("batch must be DRAFT")
            rows=conn.execute(
                """SELECT e.id,e.order_id,e.amount_sen,e.eligible_at,e.partner_id
                   FROM settlement_items si JOIN commission_entries e
                   ON e.id=si.commission_entry_id
                   WHERE si.batch_id=%s ORDER BY e.order_id,e.id""",
                (batch_id,)).fetchall()
            if not rows:
                raise SettlementApprovalError("empty batch")
            orders=sorted(set(str(row[1]) for row in rows))
            totals=defaultdict(int)
            for order_id in orders:
                order=conn.execute(
                    "SELECT status,captured_at FROM orders WHERE id=%s FOR UPDATE",
                    (order_id,)).fetchone()
                if not order or order[0] not in ("CAPTURED","PARTIALLY_REFUNDED"):
                    raise SettlementApprovalError("order status blocks approval")
                if order[1] is None or as_of < order[1]:
                    raise SettlementApprovalError("invalid approval timestamp")
                from datetime import timedelta
                if as_of < order[1]+timedelta(days=28):
                    raise SettlementApprovalError("28-day hold not elapsed")
                state=conn.execute(
                    "SELECT captured_eligible_sen,cumulative_refunded_sen FROM order_commission_state WHERE order_id=%s FOR UPDATE",
                    (order_id,)).fetchone()
                if not state or state[0] == state[1]:
                    raise SettlementApprovalError("fully refunded or missing state")
                lock=conn.execute(
                    "SELECT batch_id FROM settlement_locks WHERE order_id=%s FOR UPDATE",
                    (order_id,)).fetchone()
                if not lock or str(lock[0]) != batch_id:
                    raise SettlementApprovalError("missing or conflicting settlement lock")
                expected=conn.execute(
                    "SELECT id,amount_sen,eligible_at FROM commission_entries WHERE order_id=%s",
                    (order_id,)).fetchall()
                included={str(row[0]) for row in rows if str(row[1])==order_id}
                if any(e[2]>as_of for e in expected) or included!={str(e[0]) for e in expected}:
                    raise SettlementApprovalError("stale settlement items or pending entries")
                total=sum(e[1] for e in expected)
                if total <= 0:
                    raise SettlementApprovalError("nonpositive net commission")
                totals[order_id]=total
            # No payout: this only authorizes a reviewed immutable snapshot.
            conn.execute("UPDATE settlement_batches SET status='APPROVED' WHERE id=%s",(batch_id,))
            return {"batch_id":batch_id,"approved_by":approved_by,
                    "orders":len(orders),"total_sen":sum(totals.values())}
