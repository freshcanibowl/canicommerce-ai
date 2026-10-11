from unittest.mock import Mock
import pytest
import psycopg
from canicommerce.transaction_retry import run_with_serialization_retry

def test_retry_on_serialization_conflict():
    f=Mock(side_effect=[psycopg.errors.SerializationFailure("retry"),"ok"])
    assert run_with_serialization_retry(f,sleep=lambda _:None)=="ok"
    assert f.call_count==2

def test_do_not_retry_other_exceptions():
    f=Mock(side_effect=ValueError("bad request"))
    with pytest.raises(ValueError):
        run_with_serialization_retry(f,sleep=lambda _:None)
    assert f.call_count==1

def test_exhaustion_raises():
    f=Mock(side_effect=psycopg.errors.DeadlockDetected("deadlock"))
    with pytest.raises(psycopg.errors.DeadlockDetected):
        run_with_serialization_retry(f,max_attempts=3,sleep=lambda _:None)
    assert f.call_count==3
