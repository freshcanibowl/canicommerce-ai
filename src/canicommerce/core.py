"""Deterministic commission domain core; no network, database, or payouts."""
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from enum import Enum

ORIGINAL_RATE = Decimal("0.03")
SELLER_RATE = Decimal("0.07")

class EntryType(str, Enum):
    ORIGINAL = "ORIGINAL"
    SELLER = "SELLER"
    REVERSAL = "REVERSAL"

@dataclass(frozen=True)
class Attribution:
    customer_id: str
    original_agent_id: str
    established_at: datetime

@dataclass(frozen=True)
class CommissionEntry:
    order_id: str
    partner_id: str
    entry_type: EntryType
    amount_sen: int
    business_key: str
    created_at: datetime
    eligible_at: datetime

def commission_sen(eligible_sen: int, rate: Decimal) -> int:
    if type(eligible_sen) is not int or eligible_sen < 0:
        raise ValueError("eligible_sen must be a nonnegative integer")
    return int((Decimal(eligible_sen) * rate).quantize(Decimal("1"), rounding=ROUND_HALF_UP))

def commissions_for_capture(order_id: str, customer_id: str, eligible_sen: int,
                            original: Attribution | None, seller_partner_id: str | None,
                            captured_at: datetime) -> tuple[CommissionEntry, ...]:
    if captured_at.tzinfo is None:
        raise ValueError("captured_at must have timezone")
    if original and original.customer_id != customer_id:
        raise ValueError("attribution belongs to another customer")
    eligibility = captured_at + timedelta(days=28)
    result = []
    for kind, partner, rate in (
        (EntryType.ORIGINAL, original.original_agent_id if original else None, ORIGINAL_RATE),
        (EntryType.SELLER, seller_partner_id, SELLER_RATE),
    ):
        if partner:
            result.append(CommissionEntry(order_id, partner, kind, commission_sen(eligible_sen, rate),
                                          f"{order_id}:capture:{kind.value}", captured_at, eligibility))
    return tuple(result)

def refund_reversals(order_id: str, originals: tuple[CommissionEntry, ...],
                     total_eligible_sen: int, cumulative_refunded_sen: int,
                     prior_cumulative_refunded_sen: int, event_id: str,
                     occurred_at: datetime) -> tuple[CommissionEntry, ...]:
    if not (0 <= prior_cumulative_refunded_sen <= cumulative_refunded_sen <= total_eligible_sen):
        raise ValueError("invalid cumulative refund")
    if occurred_at.tzinfo is None:
        raise ValueError("occurred_at must have timezone")
    result = []
    for entry in originals:
        if entry.order_id != order_id or entry.entry_type == EntryType.REVERSAL:
            raise ValueError("invalid capture entry")
        rate = ORIGINAL_RATE if entry.entry_type == EntryType.ORIGINAL else SELLER_RATE
        before = commission_sen(total_eligible_sen - prior_cumulative_refunded_sen, rate)
        after = commission_sen(total_eligible_sen - cumulative_refunded_sen, rate)
        delta = after - before
        if delta:
            result.append(CommissionEntry(order_id, entry.partner_id, EntryType.REVERSAL, delta,
                f"{order_id}:refund:{event_id}:{entry.entry_type.value}", occurred_at, entry.eligible_at))
    return tuple(result)

def settlement_eligible(entries: tuple[CommissionEntry, ...], as_of: datetime,
                        disputed_orders: frozenset[str] = frozenset()) -> tuple[CommissionEntry, ...]:
    if as_of.tzinfo is None:
        raise ValueError("as_of must have timezone")
    return tuple(e for e in entries if e.eligible_at <= as_of and e.order_id not in disputed_orders)

class InMemoryLedger:
    """Demo adapter only. Production requires transactional DB unique constraints."""
    def __init__(self):
        self._entries: dict[str, CommissionEntry] = {}
    def append(self, entries: tuple[CommissionEntry, ...]) -> int:
        inserted = 0
        for entry in entries:
            old = self._entries.get(entry.business_key)
            if old is not None:
                if old != entry:
                    raise ValueError("conflicting business key")
                continue
            self._entries[entry.business_key] = entry
            inserted += 1
        return inserted
    def all(self) -> tuple[CommissionEntry, ...]:
        return tuple(self._entries.values())
