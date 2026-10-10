from datetime import datetime, timedelta, timezone
import pytest
from canicommerce.core import *

NOW = datetime(2026, 10, 10, tzinfo=timezone.utc)
A = Attribution("x", "agent-a", NOW)

def capture(seller="shop-b", original=A, sen=1200):
    return commissions_for_capture("order-1", "x", sen, original, seller, NOW)

def test_split(): assert [(x.partner_id, x.amount_sen) for x in capture()] == [("agent-a",36),("shop-b",84)]
def test_same_partner(): assert sum(x.amount_sen for x in capture("agent-a")) == 120
def test_direct_sale(): assert len(capture(None)) == 1
def test_no_referrer(): assert len(capture(original=None)) == 1
def test_zero(): assert sum(x.amount_sen for x in capture(sen=0)) == 0
def test_negative_rejected():
    with pytest.raises(ValueError): capture(sen=-1)
def test_wrong_customer():
    with pytest.raises(ValueError): capture(original=Attribution("other","a",NOW))
def test_naive_timestamp():
    with pytest.raises(ValueError): commissions_for_capture("o","x",100,A,None,datetime(2026,1,1))
def test_ledger_dedupe():
    ledger=InMemoryLedger()
    assert ledger.append(capture()) == 2
    assert ledger.append(capture()) == 0
def test_ledger_conflict():
    ledger=InMemoryLedger()
    ledger.append(capture())
    with pytest.raises(ValueError): ledger.append(capture(sen=2400))
def test_wait_28_days():
    assert settlement_eligible(capture(),NOW+timedelta(days=27)) == ()
    assert len(settlement_eligible(capture(),NOW+timedelta(days=28))) == 2
def test_dispute_blocks(): assert settlement_eligible(capture(),NOW+timedelta(days=29),frozenset({"order-1"})) == ()
def test_full_refund():
    rev=refund_reversals("order-1",capture(),1200,1200,0,"refund-1",NOW)
    assert [x.amount_sen for x in rev] == [-36,-84]
def test_partial_refund():
    rev=refund_reversals("order-1",capture(),1200,600,0,"refund-1",NOW)
    assert [x.amount_sen for x in rev] == [-18,-42]
def test_incremental_refund():
    rev=refund_reversals("order-1",capture(),1200,1200,600,"refund-2",NOW)
    assert [x.amount_sen for x in rev] == [-18,-42]
def test_invalid_refund():
    with pytest.raises(ValueError): refund_reversals("order-1",capture(),1200,1300,0,"bad",NOW)
