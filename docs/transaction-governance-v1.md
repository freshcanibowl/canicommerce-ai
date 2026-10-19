# Transaction Governance V1 — Design Contract (not production-certified)

## Goal
Decentralize control, improve security, and make every financial state transition independently auditable. This is **separation of authority**, not a claim that the system uses a blockchain or is trustless.

## Non-negotiable invariants
1. No client, agent, seller, or AI output is authoritative proof of payment. A verified provider capture and immutable server-side order mapping are mandatory.
2. Every capture has a globally unique provider-event identity; exact replays are no-ops and conflicting replays are rejected. No second capture can create additional commissions for a captured order.
3. Commission base is eligible net MYR sen excluding taxes, shipping and refunded amounts. Original Agent earns 3% recurring and Selling Partner earns 7% per sale; both can earn on the same order. No multi-level attribution.
4. Financial evidence is append-only. Refunds and chargebacks create compensating entries, never edits or deletes of posted ledger entries.
5. No single role may both create/modify the transaction evidence and approve/execute its settlement. Worker cannot read settlement/audit data or write payout records. Approvals must be independently authenticated and persisted.
6. Settlement requires provider reconciliation, refund/chargeback checks, at least 28 days of hold, and a separate authorized approval. Payout remains disabled until controls and real sandbox evidence pass.
7. Every state transition records actor/service identity, timestamp, event ID, order ID, reason, correlation ID, and prior-state reference. Sensitive customer data must not appear in public proofs.
8. Corrections are new signed/auditable events with reason and reference to prior entries. Reject missing or duplicate authorization.
9. Partner-facing transparency is **scoped**: each partner can see only their own accruals, holds, reversals and settlement evidence. Public transparency must be aggregate or cryptographic proof only, never personal/order details.
10. A tamper-evident hash chain or Merkle checkpoint anchored to independent storage is a future enhancement; until independently verified, do not claim immutable or decentralized infrastructure.

## Authority matrix
| Operation | Requester | Trusted verifier | Independent authorizer | Ledger writer |
|---|---|---|---|---|
| Order placement | Customer / partner | Server validation | N/A | Order service |
| Capture | Payment provider webhook | Server-side provider GET and signature | N/A | Restricted capture worker |
| Attribution | Registered referral event | Immutable attribution policy | Separate correction authority | Attribution service |
| Refund | Authorized operator/provider | Provider refund confirmation | Policy-controlled approval | Refund service |
| Settlement | Settlement service | Reconciliation and hold gate | Separate settlement approver | Settlement worker |
| Payout | Payout service | Provider and beneficiary verification | Dual control | Dedicated payout worker (future) |

## Acceptance gates
- G1: Unit tests prove commission math, rounding, refund allocation and no second capture.
- G2: Disposable PostgreSQL tests prove worker least privilege and append-only invariants.
- G3: Concurrent capture/refund/settlement race tests and idempotency across restarts.
- G4: Provider sandbox signature, capture GET, amount/currency/merchant verification, refund and dispute replay evidence.
- G5: Independent settlement approval, audit trail, 28-day hold, reconciliation and scoped partner statements.
- G6: Threat model, restore drill, log redaction, access review, external auditability.
- G7: Only after G1–G6 pass: controlled payout pilot; production release requires explicit approval.

## Current status
Design policy only. Existing repository includes capture/ledger/security components but CI currently fails before execution; this document does not certify their correctness. Do not merge main, modify production, or enable live payouts.
