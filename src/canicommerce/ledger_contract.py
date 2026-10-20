"""Provider-agnostic ledger transaction contract.

No DB connection or payment signature verification is implemented here.
An adapter must run all operations in one SERIALIZABLE DB transaction,
with unique(provider, event_id) and unique(business_key) constraints.
"""
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

class PaymentEventKind(str, Enum):
    CAPTURE = "CAPTURE"
    REFUND = "REFUND"
    DISPUTE_OPENED = "DISPUTE_OPENED"
    DISPUTE_RESOLVED = "DISPUTE_RESOLVED"

@dataclass(frozen=True)
class VerifiedPaymentEvent:
    provider: str
    provider_event_id: str
    order_id: str
    kind: PaymentEventKind
    occurred_at: datetime
    payload_sha256: str
    # This type must ONLY be instantiated by a trusted signature-verifying adapter.

    def __post_init__(self):
        if not self.provider or not self.provider_event_id or not self.order_id:
            raise ValueError("provider, event and order identifiers required")
        if len(self.payload_sha256) != 64 or any(c not in "0123456789abcdef" for c in self.payload_sha256):
            raise ValueError("expected lowercase SHA256 digest")
        if self.occurred_at.tzinfo is None:
            raise ValueError("timezone-aware event timestamp required")

@dataclass(frozen=True)
class SettlementDecision:
    order_id: str
    eligible: bool
    reason: str

def decide_settlement(order_id: str, captured_at: datetime, as_of: datetime,
                      refunded_sen: int, captured_sen: int,
                      disputed: bool, already_locked: bool) -> SettlementDecision:
    from datetime import timedelta
    if captured_at.tzinfo is None or as_of.tzinfo is None:
        raise ValueError("timestamps must be timezone aware")
    if captured_sen < 0 or not 0 <= refunded_sen <= captured_sen:
        raise ValueError("invalid refund state")
    if already_locked:
        return SettlementDecision(order_id, False, "ALREADY_LOCKED")
    if disputed:
        return SettlementDecision(order_id, False, "DISPUTED")
    if as_of < captured_at + timedelta(days=28):
        return SettlementDecision(order_id, False, "WAIT_28_DAYS")
    if captured_sen == refunded_sen:
        return SettlementDecision(order_id, False, "FULLY_REFUNDED")
    return SettlementDecision(order_id, True, "ELIGIBLE")
