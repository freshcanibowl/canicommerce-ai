"""PostgreSQL atomic capture, refund, settlement-claim prototype.

Requires psycopg 3, migrated schema, and trusted provider verification upstream.
Never pass unverified payment payloads to these methods.
"""
from datetime import datetime, timedelta
from uuid import uuid4
import psycopg
from psycopg.errors import SerializationFailure
from .core import Attribution, commissions_for_capture, refund_reversals, CommissionEntry, EntryType

class FinancialConflict(ValueError): pass

class PostgresCommissionRepository:
    def __init__(self, dsn: str):
        self.dsn = dsn

    def capture(self, *, order_id: str, provider: str, event_id: str,
                payload_hash: str, customer_id: str, eligible_sen: int,
                captured_at: datetime) -> bool:
        """Return True if first successful capture, False for exact duplicate.
        SERIALIZABLE + order row lock ensures different events cannot double-award.
        """
        with psycopg.connect(self.dsn) as conn:
            with conn.transaction():
                conn.execute("SET TRANSACTION ISOLATION LEVEL SERIALIZABLE")
                order = conn.execute(
                    "SELECT customer_id, eligible_net_sen, status, selling_partner_id, captured_at FROM orders WHERE id=%s FOR UPDATE",
                    (order_id,)).fetchone()
                if order is None or str(order[0]) != customer_id or order[1] != eligible_sen:
                    raise FinancialConflict("order ownership or amount mismatch")
                if order[2] not in ("PENDING", "CAPTURED"):
                    raise FinancialConflict("invalid order status")
                previous = conn.execute(
                    "SELECT order_id,payload_hash FROM processed_payment_events WHERE provider=%s AND provider_event_id=%s",
                    (provider,event_id)).fetchone()
                if previous:
                    if str(previous[0]) != order_id or previous[1] != payload_hash:
                        raise FinancialConflict("event identifier reused with conflicting payload")
                    return False
                if order[2] == "CAPTURED":
                    raise FinancialConflict("second capture event for same order")
                original = conn.execute(
                    """SELECT original_agent_id, effective_at FROM customer_attributions
                       WHERE customer_id=%s AND corrected_at IS NULL
                       ORDER BY effective_at DESC LIMIT 1""",(customer_id,)).fetchone()
                attribution = Attribution(customer_id,str(original[0]),original[1]) if original else None
                entries=commissions_for_capture(order_id,customer_id,eligible_sen,attribution,
                    str(order[3]) if order[3] else None,captured_at)
                conn.execute(
                    """INSERT INTO processed_payment_events(provider,provider_event_id,order_id,payload_hash)
                       VALUES (%s,%s,%s,%s)""",(provider,event_id,order_id,payload_hash))
                conn.execute("UPDATE orders SET status='CAPTURED', captured_at=%s WHERE id=%s",
                             (captured_at,order_id))
                conn.execute(
                    "INSERT INTO order_commission_state(order_id,captured_eligible_sen) VALUES (%s,%s)",
                    (order_id,eligible_sen))
                for entry in entries:
                    conn.execute(
                        """INSERT INTO commission_entries
                        (id,order_id,partner_id,entry_type,amount_sen,business_key,eligible_at,created_at)
                        VALUES (%s,%s,%s,%s,%s,%s,%s,%s)""",
                        (str(uuid4()),order_id,entry.partner_id,entry.entry_type.value,
                         entry.amount_sen,entry.business_key,entry.eligible_at,entry.created_at))
                return True

    def refund(self, *, order_id: str, provider: str, event_id: str,
               payload_hash: str, cumulative_refunded_sen: int, occurred_at: datetime) -> bool:
        """Refund is serialized with settlement claim via order row lock.
        Existing PAID settlements require recovery workflow (blocked here).
        """
        with psycopg.connect(self.dsn) as conn:
            with conn.transaction():
                conn.execute("SET TRANSACTION ISOLATION LEVEL SERIALIZABLE")
                order=conn.execute(
                    "SELECT status FROM orders WHERE id=%s FOR UPDATE",(order_id,)).fetchone()
                if order is None or order[0] not in ("CAPTURED","PARTIALLY_REFUNDED"):
                    raise FinancialConflict("order not refundable")
                prev_event=conn.execute(
                    "SELECT order_id,payload_hash FROM processed_payment_events WHERE provider=%s AND provider_event_id=%s",
                    (provider,event_id)).fetchone()
                if prev_event:
                    if str(prev_event[0]) != order_id or prev_event[1] != payload_hash:
                        raise FinancialConflict("conflicting duplicate refund")
                    return False
                state=conn.execute(
                    "SELECT captured_eligible_sen,cumulative_refunded_sen FROM order_commission_state WHERE order_id=%s FOR UPDATE",
                    (order_id,)).fetchone()
                if state is None or not state[1] < cumulative_refunded_sen <= state[0]:
                    raise FinancialConflict("refund not monotonic or exceeds capture")
                if conn.execute(
                    """SELECT 1 FROM settlement_locks l JOIN settlement_batches b ON b.id=l.batch_id
                       WHERE l.order_id=%s AND b.status IN ('APPROVED','PAID')""",
                    (order_id,)).fetchone():
                    raise FinancialConflict("settled refund needs recovery workflow")
                rows=conn.execute(
                    """SELECT partner_id,entry_type,amount_sen,business_key,created_at,eligible_at
                       FROM commission_entries WHERE order_id=%s AND entry_type IN ('ORIGINAL','SELLER')""",
                    (order_id,)).fetchall()
                entries=tuple(CommissionEntry(order_id,str(r[0]),EntryType(r[1]),r[2],r[3],r[4],r[5]) for r in rows)
                reversals=refund_reversals(order_id,entries,state[0],cumulative_refunded_sen,
                                          state[1],event_id,occurred_at)
                conn.execute(
                    "INSERT INTO processed_payment_events(provider,provider_event_id,order_id,payload_hash) VALUES (%s,%s,%s,%s)",
                    (provider,event_id,order_id,payload_hash))
                for e in reversals:
                    conn.execute(
                        """INSERT INTO commission_entries
                           (id,order_id,partner_id,entry_type,amount_sen,business_key,eligible_at,created_at)
                           VALUES (%s,%s,%s,'REVERSAL',%s,%s,%s,%s)""",
                        (str(uuid4()),order_id,e.partner_id,e.amount_sen,e.business_key,e.eligible_at,e.created_at))
                conn.execute(
                    "UPDATE order_commission_state SET cumulative_refunded_sen=%s WHERE order_id=%s",
                    (cumulative_refunded_sen,order_id))
                conn.execute("UPDATE orders SET status=%s WHERE id=%s",
                             ("REFUNDED" if cumulative_refunded_sen==state[0] else "PARTIALLY_REFUNDED",order_id))
                return True

    def claim_settlement(self, *, order_id: str, batch_id: str, as_of: datetime) -> bool:
        """Claims eligibility; does not approve, pay, or transfer money."""
        with psycopg.connect(self.dsn) as conn:
            with conn.transaction():
                conn.execute("SET TRANSACTION ISOLATION LEVEL SERIALIZABLE")
                order=conn.execute(
                    "SELECT status,captured_at FROM orders WHERE id=%s FOR UPDATE",
                    (order_id,)).fetchone()
                if not order or order[0] not in ("CAPTURED","PARTIALLY_REFUNDED"):
                    return False
                if order[1] is None or as_of < order[1]+timedelta(days=28):
                    return False
                state=conn.execute(
                    "SELECT captured_eligible_sen,cumulative_refunded_sen FROM order_commission_state WHERE order_id=%s",
                    (order_id,)).fetchone()
                if not state or state[0] == state[1]:
                    return False
                if conn.execute("SELECT 1 FROM settlement_locks WHERE order_id=%s",(order_id,)).fetchone():
                    return False
                batch=conn.execute("SELECT status FROM settlement_batches WHERE id=%s FOR UPDATE",(batch_id,)).fetchone()
                if not batch or batch[0] != "DRAFT":
                    raise FinancialConflict("batch must be draft")
                conn.execute("INSERT INTO settlement_locks(order_id,batch_id) VALUES (%s,%s)",(order_id,batch_id))
                rows=conn.execute(
                    "SELECT id FROM commission_entries WHERE order_id=%s AND eligible_at<=%s",
                    (order_id,as_of)).fetchall()
                for (entry_id,) in rows:
                    conn.execute(
                        "INSERT INTO settlement_items(batch_id,commission_entry_id) VALUES (%s,%s)",
                        (batch_id,entry_id))
                return True
