# CaniCommerce × CaniBiz — isolated integration Build 02

## Source audit (2026-10-29)
- `freshcanibowl/canicommerce-ai` main: deterministic commission domain in `src/canicommerce/core.py`, draft PostgreSQL schema, tests; not production.
- Hackathon branch `hackathon/web3-social-good-2026`: synthetic data Merkle proof and Sepolia receipt verification; source for this integration branch.
- `freshcanibowl/canibiz-partner-commission-os`: `main` and `build/v1.8-staging-import` README both declare **bootstrap only** and V1.8 not migrated or cloud-tested. No proven operational backend to import.

## Integration contract
1. Keep 3% original attribution and 7% seller default. No phantom seller for direct orders; one partner may receive both.
2. Eligible product net amount in integer sen only; exclude fees/delivery. Round half-up.
3. 28 calendar days only after **verified** payment success; disputes block eligibility.
4. Append reversals for refunds; deduplicate payment events transactionally before production.
5. Record every admin policy change with authenticated actor, before/after, reason, approval and policy version. Historical entries must not be silently recalculated.
6. Proofs operate on immutable snapshots; Merkle root must be anchored separately on-chain before claiming chain verification.
7. Never copy private CAIOS data or merge `main`. No payments, wallets or real commissions until independent security/finance acceptance.

## Architecture
- Business engine: Python `src/canicommerce/core.py` (currently static percentage constants).
- Proof engine: `hackathon/proof-of-fair-commission/` (SHA-256 Merkle + receipt verifier).
- Admin UI: separate V0.6 static prototype **not yet committed or connected to backend**.
- Future API: scoped FastAPI endpoints with RBAC, approved policy versions, append-only DB audit, settlement gating, and read-only proof exports.
- PostgreSQL migration: draft only. Must receive constraints, RLS, idempotent webhook handling, audit history and locking.

## Ship gates
- Gate 0 PASS: repository inventory and safe isolation branch.
- Gate 1 OPEN: ingest verified CaniBiz V1.8 source package; map models and migration conflicts.
- Gate 2 OPEN: DB-backed policy version and audit with auth/RBAC.
- Gate 3 OPEN: transaction-safe payments/refunds/28-day settlement.
- Gate 4 OPEN: service endpoints connected to web UI; E2E and security tests.
- Gate 5 OPEN: independently verify new snapshot receipt; deploy staging; rollback and monitoring.
