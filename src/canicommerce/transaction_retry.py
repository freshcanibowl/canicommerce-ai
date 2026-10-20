"""Retry ONLY database serialization/deadlock errors.

Caller must ensure a stable provider event ID and idempotent business keys.
Never retry arbitrary payment gateway calls or unknown exceptions.
"""
import time
import psycopg

def run_with_serialization_retry(operation, *, max_attempts=3, sleep=time.sleep):
    if max_attempts < 1 or max_attempts > 10:
        raise ValueError("max_attempts must be between 1 and 10")
    for attempt in range(max_attempts):
        try:
            return operation()
        except (psycopg.errors.SerializationFailure, psycopg.errors.DeadlockDetected):
            if attempt+1 == max_attempts:
                raise
            sleep(0.02 * (2 ** attempt))
