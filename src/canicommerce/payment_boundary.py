"""Fail-closed payment verification boundary.

Only a provider adapter may construct a VerifiedCapture after independent
signature and provider API reconciliation. This module does NOT verify PayPal
signatures itself; it refuses unverified or inconsistent claims.
"""
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json

class PaymentVerificationError(ValueError):
    pass

@dataclass(frozen=True)
class VerifiedCapture:
    provider: str
    provider_event_id: str
    order_id: str
    provider_capture_id: str
    currency: str
    gross_sen: int
    eligible_net_sen: int
    verified_at: datetime
    payload_hash: str

def verified_capture_from_provider(*, provider: str, event_id: str,
                                   order_id: str, capture_id: str,
                                   currency: str, gross_sen: int,
                                   eligible_net_sen: int,
                                   provider_signature_verified: bool,
                                   provider_capture_confirmed: bool,
                                   provider_order_id: str,
                                   provider_currency: str,
                                   provider_gross_sen: int,
                                   raw_payload: bytes,
                                   verified_at: datetime) -> VerifiedCapture:
    """Require independently verified signature and capture lookup.
    Flags must originate in a trusted server-side adapter, never user input.
    """
    if not provider_signature_verified or not provider_capture_confirmed:
        raise PaymentVerificationError("provider signature and capture confirmation required")
    if not all((provider,event_id,order_id,capture_id)) or not raw_payload:
        raise PaymentVerificationError("missing required payment identity")
    if provider_order_id != order_id or provider_currency != currency or provider_gross_sen != gross_sen:
        raise PaymentVerificationError("provider capture reconciliation mismatch")
    if currency != "MYR" or isinstance(gross_sen,bool) or isinstance(eligible_net_sen,bool):
        raise PaymentVerificationError("unsupported currency or invalid money type")
    if not isinstance(gross_sen,int) or not isinstance(eligible_net_sen,int):
        raise PaymentVerificationError("money must use integer sen")
    if not (0 <= eligible_net_sen <= gross_sen):
        raise PaymentVerificationError("invalid eligible net revenue")
    if verified_at.tzinfo is None or verified_at.utcoffset() is None:
        raise PaymentVerificationError("verified_at must include timezone")
    return VerifiedCapture(provider,event_id,order_id,capture_id,currency,gross_sen,
                           eligible_net_sen,verified_at,sha256(raw_payload).hexdigest())
