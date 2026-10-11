from datetime import datetime, timezone
import pytest
from canicommerce.payment_boundary import (
    verified_capture_from_provider, PaymentVerificationError
)

def valid():
    return dict(provider="paypal-sandbox",event_id="WH-1",order_id="ORDER-1",
                capture_id="CAPTURE-1",currency="MYR",gross_sen=1200,
                eligible_net_sen=1000,provider_signature_verified=True,
                provider_capture_confirmed=True,provider_order_id="ORDER-1",
                provider_currency="MYR",provider_gross_sen=1200,
                raw_payload=b'{"event":"capture"}',
                verified_at=datetime(2026,10,11,tzinfo=timezone.utc))

def test_accept_reconciled_capture():
    v=verified_capture_from_provider(**valid())
    assert v.eligible_net_sen==1000
    assert len(v.payload_hash)==64

@pytest.mark.parametrize("field,value",[
    ("provider_signature_verified",False),
    ("provider_capture_confirmed",False),
    ("provider_order_id","OTHER"),
    ("provider_currency","USD"),
    ("provider_gross_sen",1199),
    ("currency","USD"),
    ("eligible_net_sen",1201),
    ("eligible_net_sen",-1),
    ("gross_sen",12.5),
    ("eligible_net_sen",True),
    ("raw_payload",b""),
    ("verified_at",datetime(2026,10,11)),
])
def test_reject_unverified_or_inconsistent_capture(field,value):
    data=valid()
    data[field]=value
    with pytest.raises(PaymentVerificationError):
        verified_capture_from_provider(**data)
