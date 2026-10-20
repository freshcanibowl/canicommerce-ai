"""Trusted provider mapping and commission capture handoff.

Only call register_mapping from server-side PayPal order creation.
Never use webhook-supplied local order/customer/eligible net as authority.
"""
from uuid import uuid4
import psycopg
from canicommerce.payment_boundary import VerifiedCapture
from canicommerce.postgres_repository import PostgresCommissionRepository
from canicommerce.transaction_retry import run_with_serialization_retry

class ProviderMappingError(ValueError):
    pass

def register_mapping(dsn: str, *, local_order_id: str, provider_order_id: str,
                     expected_merchant_id: str, expected_gross_sen: int):
    if not all((local_order_id,provider_order_id,expected_merchant_id)) or expected_gross_sen<=0:
        raise ProviderMappingError("invalid provider mapping")
    with psycopg.connect(dsn) as conn:
        with conn.transaction():
            conn.execute("SET TRANSACTION ISOLATION LEVEL SERIALIZABLE")
            order=conn.execute("SELECT status,currency FROM orders WHERE id=%s FOR UPDATE",
                               (local_order_id,)).fetchone()
            if not order or order[0]!="PENDING" or order[1]!="MYR":
                raise ProviderMappingError("local order not pending MYR")
            conn.execute(
                """INSERT INTO provider_order_mappings
                   (id,provider,provider_order_id,local_order_id,expected_merchant_id,expected_gross_sen)
                   VALUES (%s,'paypal-sandbox',%s,%s,%s,%s)""",
                (str(uuid4()),provider_order_id,local_order_id,expected_merchant_id,expected_gross_sen))

def capture_verified(dsn: str, *, capture: VerifiedCapture,
                     local_order_id: str, customer_id: str) -> bool:
    return run_with_serialization_retry(lambda: _capture_verified_once(
        dsn, capture=capture, local_order_id=local_order_id, customer_id=customer_id))


def _capture_verified_once(dsn: str, *, capture: VerifiedCapture,
                           local_order_id: str, customer_id: str) -> bool:
    """Verify trusted mapping and immutable local amount before posting commissions.

    Mapping, capture reservation, payment event, order state and commissions
    commit or roll back together under one SERIALIZABLE transaction.
    """
    if not isinstance(capture,VerifiedCapture) or capture.provider!="paypal-sandbox":
        raise ProviderMappingError("verified sandbox capture required")
    with psycopg.connect(dsn) as conn:
        with conn.transaction():
            conn.execute("SET TRANSACTION ISOLATION LEVEL SERIALIZABLE")
            mapping=conn.execute(
                """SELECT local_order_id,expected_gross_sen
                   FROM provider_order_mappings WHERE provider=%s AND provider_order_id=%s""",
                (capture.provider,capture.order_id)).fetchone()
            if not mapping or str(mapping[0])!=local_order_id or mapping[1]!=capture.gross_sen:
                raise ProviderMappingError("provider/local order or gross amount mismatch")
            order=conn.execute(
                "SELECT customer_id,eligible_net_sen FROM orders WHERE id=%s FOR UPDATE",
                (local_order_id,)).fetchone()
            if not order or str(order[0])!=customer_id or order[1]!=capture.eligible_net_sen:
                raise ProviderMappingError("trusted local customer/net mismatch")
            existing=conn.execute(
                "SELECT provider_order_id,local_order_id FROM provider_capture_mappings WHERE provider=%s AND provider_capture_id=%s",
                (capture.provider,capture.provider_capture_id)).fetchone()
            if existing:
                if existing[0]!=capture.order_id or str(existing[1])!=local_order_id:
                    raise ProviderMappingError("capture ID replayed for another order")
            other_capture=conn.execute(
                "SELECT provider_capture_id FROM provider_capture_mappings WHERE provider=%s AND local_order_id=%s",
                (capture.provider,local_order_id)).fetchone()
            if other_capture and other_capture[0]!=capture.provider_capture_id:
                raise ProviderMappingError("second capture ID for local order")
            if not existing:
                conn.execute(
                    """INSERT INTO provider_capture_mappings
                       (id,provider,provider_capture_id,provider_order_id,local_order_id)
                       VALUES (%s,%s,%s,%s,%s)""",
                    (str(uuid4()),capture.provider,capture.provider_capture_id,capture.order_id,local_order_id))
            return PostgresCommissionRepository(dsn).capture(
                order_id=local_order_id,provider=capture.provider,
                event_id=capture.provider_event_id,payload_hash=capture.payload_hash,
                customer_id=customer_id,eligible_sen=capture.eligible_net_sen,
                captured_at=capture.verified_at,connection=conn)
