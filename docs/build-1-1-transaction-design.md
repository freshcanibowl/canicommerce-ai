# Build 1.1 — Transactional Ledger Contract

**Status: design + migration draft + deterministic tests. Not a PostgreSQL adapter or production-ready payment service.**

## CAPTURE transaction
1. Verify payment signature and event ownership *before* constructing VerifiedPaymentEvent.
2. BEGIN transaction at SERIALIZABLE isolation; acquire order row lock.
3. INSERT processed_payment_events (provider, event_id, payload hash) ON CONFLICT DO NOTHING.
4. If duplicate: compare stored order ID and hash; return idempotent success only on exact match, otherwise flag security conflict.
5. Validate captured order amount and currency against server-priced order; reject mismatches.
6. Lock original customer attribution, then insert deterministic ORIGINAL 3% and SELLER 7% entries with unique business keys.
7. Commit atomically; retry serialization failures with bounded backoff.

## REFUND transaction
1. Verify refund event; lock order_commission_state row.
2. Compare provider-authoritative cumulative refund to stored cumulative refund.
3. Reject regression or over-refund; compute delta reversal with core.refund_reversals.
4. Append negative entries, advance cumulative refund, commit together.
5. If a settlement was already paid, record a recoverable partner balance or manual collection case; never silently erase history.

## SETTLEMENT transaction
1. Find orders captured at least 28 days ago.
2. Lock eligible order rows using FOR UPDATE SKIP LOCKED.
3. Exclude active disputes, unsettled refunds and already locked/paid entries.
4. Create settlement batch + items + order locks in a single transaction.
5. Approval and payout require separate authenticated operator and reconciliation steps.

## Attribution correction
Never rewrite original attribution silently. Corrections require actor, reason,
effective time, and auditable supersession. Resolve conflicts before payment
and define compensating adjustments after payment.

## Explicit non-goals
No live payments, payout, production DB migration, public APIs, Web3 or CAIOS integration.
