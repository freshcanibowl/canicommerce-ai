from datetime import datetime, timedelta, timezone
import pytest
from canicommerce.ledger_contract import PaymentEventKind, VerifiedPaymentEvent, decide_settlement

NOW = datetime(2026, 10, 10, tzinfo=timezone.utc)
HASH = "a" * 64

def test_verified_event_shape():
    x=VerifiedPaymentEvent("paypal","evt-1","order-1",PaymentEventKind.CAPTURE,NOW,HASH)
    assert x.kind == PaymentEventKind.CAPTURE
def test_missing_event_id():
    with pytest.raises(ValueError):
        VerifiedPaymentEvent("paypal","","order-1",PaymentEventKind.CAPTURE,NOW,HASH)
def test_invalid_digest():
    with pytest.raises(ValueError):
        VerifiedPaymentEvent("paypal","evt","order",PaymentEventKind.REFUND,NOW,"bad")
def test_timezone_required():
    with pytest.raises(ValueError):
        VerifiedPaymentEvent("paypal","evt","order",PaymentEventKind.CAPTURE,datetime(2026,1,1),HASH)
@pytest.mark.parametrize("disputed,locked,refund,days,reason",[
    (False,False,0,27,"WAIT_28_DAYS"),
    (True,False,0,29,"DISPUTED"),
    (False,True,0,29,"ALREADY_LOCKED"),
    (False,False,1200,29,"FULLY_REFUNDED"),
    (False,False,600,28,"ELIGIBLE"),
])
def test_settlement_gate(disputed,locked,refund,days,reason):
    x=decide_settlement("o",NOW,NOW+timedelta(days=days),refund,1200,disputed,locked)
    assert x.reason==reason
def test_invalid_refund():
    with pytest.raises(ValueError):
        decide_settlement("o",NOW,NOW,1300,1200,False,False)
