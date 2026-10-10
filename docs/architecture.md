# Architecture boundary

CaniCommerce AI is an isolated prototype, not CAIOS, CaniPay or Journey Plus.

Capture event (verified by a future payment adapter)
→ Order state → Original-agent attribution + selling partner
→ Deterministic 3% / 7% entries → Append-only ledger
→ 28-day eligibility → Dispute/refund review → Approved settlement.

Amounts are integer MYR sen, rounded half-up per commission line.
The original referring agent receives 3% of eligible net product revenue;
the selling partner receives 7%; the same partner can receive both.

**Current limitations:** no HTTP API, real payment capture, DB-backed atomicity,
auth, payouts, live deployment or multi-tenant enforcement. The migration is a
schema draft; the Python in-memory ledger is for unit tests only.
