"""Offline PayPal capture evidence parser. NO API calls or money movement."""
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Mapping, Any

class EvidenceError(ValueError):
    pass

@dataclass(frozen=True)
class ExpectedPayment:
    order_id: str
    amount_minor: int
    currency: str
    merchant_id: str
    exponent: int = 2

    def __post_init__(self):
        if not all(isinstance(x, str) and x.strip() for x in (self.order_id, self.currency, self.merchant_id)):
            raise EvidenceError("missing identity")
        if type(self.amount_minor) is not int or self.amount_minor <= 0:
            raise EvidenceError("invalid expected amount")
        if len(self.currency) != 3 or not self.currency.isascii() or not self.currency.isalpha() or self.currency != self.currency.upper():
            raise EvidenceError("invalid currency")
        if self.exponent not in (0, 2, 3):
            raise EvidenceError("unsupported exponent")

@dataclass(frozen=True)
class ParsedCapture:
    capture_id: str
    order_id: str
    merchant_id: str
    amount_minor: int
    currency: str
    evidence_level: str = "UNAUTHENTICATED_PAYLOAD_PARSED"

def parse_minor(value: str, exponent: int) -> int:
    if not isinstance(value, str):
        raise EvidenceError("amount must be a string")
    try:
        d = Decimal(value)
    except (InvalidOperation, ValueError):
        raise EvidenceError("invalid amount") from None
    if not d.is_finite() or d <= 0 or (d * 10**exponent) != (d * 10**exponent).to_integral_value():
        raise EvidenceError("invalid amount precision or sign")
    return int(d * 10**exponent)

def parse_paypal_capture(payload: Mapping[str, Any], expected: ExpectedPayment,
                         *, authenticated_order_id: str, authenticated_merchant_id: str) -> ParsedCapture:
    """Validate fields only; caller MUST authenticate the provider response, order and merchant binding.

    Never use this function alone as a basis for posting commission entries.
    The order and merchant IDs must be independently verified against trusted server-side state.
    """
    if not isinstance(payload, Mapping):
        raise EvidenceError("invalid capture payload")
    if authenticated_order_id != expected.order_id or authenticated_merchant_id != expected.merchant_id:
        raise EvidenceError("trusted order/merchant mismatch")
    if payload.get("status") != "COMPLETED":
        raise EvidenceError("capture not completed")
    cid = payload.get("id")
    if not isinstance(cid, str) or not cid.strip():
        raise EvidenceError("missing capture ID")
    amount = payload.get("amount")
    if not isinstance(amount, Mapping) or amount.get("currency_code") != expected.currency:
        raise EvidenceError("currency mismatch")
    minor = parse_minor(amount.get("value"), expected.exponent)
    if minor != expected.amount_minor:
        raise EvidenceError("amount mismatch")
    extra = payload.get("supplementary_data")
    if isinstance(extra, Mapping):
        related = extra.get("related_ids")
        if isinstance(related, Mapping) and related.get("order_id") is not None and related["order_id"] != expected.order_id:
            raise EvidenceError("related order mismatch")
    return ParsedCapture(cid, expected.order_id, expected.merchant_id, minor, expected.currency)
