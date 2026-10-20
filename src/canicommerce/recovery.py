"""Append-only recovery obligations for verified post-approval refunds.

This records liabilities only. Does not debit partners or move money.
Upstream MUST verify provider signature, refund amount and event identity.
"""
from decimal import Decimal, ROUND_HALF_UP
from uuid import uuid4
import psycopg

class RecoveryConflict(ValueError):
    pass

def _round_sen(amount: int, numerator: int, denominator: int) -> int:
    return int((Decimal(amount) * Decimal(numerator) / Decimal(denominator))
               .quantize(Decimal("1"), rounding=ROUND_HALF_UP))

def record_post_approval_refund(dsn: str, *, order_id: str, provider: str,
                                event_id: str, payload_hash: str,
                                cumulative_refunded_sen: int, occurred_at) -> dict:
    """Serialize on order; create partner obligations proportional to cumulative refund.
    Reject repeated event with altered hash and nonmonotonic amounts.
    """
    with psycopg.connect(dsn) as conn:
        with conn.transaction():
            conn.execute("SET TRANSACTION ISOLATION LEVEL SERIALIZABLE")
            order=conn.execute("SELECT status FROM orders WHERE id=%s FOR UPDATE",(order_id,)).fetchone()
            if not order or order[0] not in ("CAPTURED","PARTIALLY_REFUNDED"):
                raise RecoveryConflict("order not eligible for recovery")
            event=conn.execute(
                "SELECT order_id,payload_hash FROM processed_payment_events WHERE provider=%s AND provider_event_id=%s",
                (provider,event_id)).fetchone()
            if event:
                if str(event[0]) != order_id or event[1] != payload_hash:
                    raise RecoveryConflict("conflicting provider event")
                return {"duplicate":True,"obligations":0}
            state=conn.execute(
                "SELECT captured_eligible_sen,cumulative_refunded_sen FROM order_commission_state WHERE order_id=%s FOR UPDATE",
                (order_id,)).fetchone()
            if not state or not state[1] < cumulative_refunded_sen <= state[0]:
                raise RecoveryConflict("invalid cumulative refund")
            lock=conn.execute(
                """SELECT b.status FROM settlement_locks l JOIN settlement_batches b ON b.id=l.batch_id
                   WHERE l.order_id=%s FOR UPDATE OF b""",(order_id,)).fetchone()
            if not lock or lock[0] not in ("APPROVED","PAID"):
                raise RecoveryConflict("requires approved or paid settlement")
            base=conn.execute(
                """SELECT partner_id,amount_sen FROM commission_entries
                   WHERE order_id=%s AND entry_type IN ('ORIGINAL','SELLER')""",(order_id,)).fetchall()
            if not base:
                raise RecoveryConflict("missing original commissions")
            already=conn.execute(
                """SELECT partner_id,COALESCE(SUM(amount_sen),0) FROM recovery_obligations
                   WHERE order_id=%s GROUP BY partner_id""",(order_id,)).fetchall()
            prior={str(p):int(a) for p,a in already}
            obligations=[]
            for partner,original_sen in base:
                target=_round_sen(int(original_sen),cumulative_refunded_sen,state[0])
                delta=target-prior.get(str(partner),0)
                if delta < 0:
                    raise RecoveryConflict("recovery history exceeds target")
                if delta:
                    obligations.append((str(partner),delta))
            conn.execute(
                """INSERT INTO processed_payment_events(provider,provider_event_id,order_id,payload_hash)
                   VALUES (%s,%s,%s,%s)""",(provider,event_id,order_id,payload_hash))
            reason="POST_PAYOUT_REFUND" if lock[0]=="PAID" else "POST_APPROVAL_REFUND"
            for partner,amount in obligations:
                conn.execute(
                    """INSERT INTO recovery_obligations
                    (id,order_id,partner_id,provider,provider_event_id,amount_sen,reason,occurred_at)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s)""",
                    (str(uuid4()),order_id,partner,provider,event_id,amount,reason,occurred_at))
            conn.execute(
                "UPDATE order_commission_state SET cumulative_refunded_sen=%s WHERE order_id=%s",
                (cumulative_refunded_sen,order_id))
            conn.execute(
                "UPDATE orders SET status=%s WHERE id=%s",
                ("REFUNDED" if cumulative_refunded_sen==state[0] else "PARTIALLY_REFUNDED",order_id))
            return {"duplicate":False,"obligations":len(obligations),
                    "new_recovery_sen":sum(amount for _,amount in obligations)}
