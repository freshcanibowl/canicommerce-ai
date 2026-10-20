# Build 1.4 concurrency / settlement risk register

## Implemented test probes
- Two concurrent distinct capture events for the same order; only one commission pair may exist.
- Full refund racing a draft settlement claim; the test ensures no PAID batch is created.

## Critical known limitations
1. SERIALIZABLE transactions can abort with serialization failure; repository does not retry yet.
2. A DRAFT settlement claim can race a refund and retain a stale settlement item set. A settlement approval guard must recompute eligible balance and block/rebuild stale claims.
3. A refund after APPROVED or PAID is intentionally blocked, but a recovery/debt ledger is still missing.
4. Provider signatures, payment amount reconciliation, refund verification, RBAC/RLS and payouts are not implemented.
5. Tests accept serialization rejection as safe, not as successful business completion.
6. No production database or actual PayPal capture has been exercised.

## Gate before payout
Add approval-time validation with row locks, settlement net balance recomputation,
dispute state, provider refund reconciliation, and a recovery ledger.
Run a concurrent refund-versus-approval test and assert payout cannot exceed
the net commission due. No payout until all these gates pass.
