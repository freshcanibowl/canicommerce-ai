# CaniCommerce × CaniBiz — Integrated Pilot Build 01

An **isolated, deployable synthetic demonstration**, combining code already present in `freshcanibowl/canicommerce-ai`, frozen commercial rules documented in the private `freshcanibowl/canibiz-partner-commission-os`, and the hackathon Sepolia proof implementation from `hackathon/web3-social-good-2026`.

**Source disclosure:** The CaniBiz repository currently contains only its README and says the earlier V1.8 implementation has not been migrated. Therefore this package does **not** claim to incorporate an unseen V1.8 implementation. The attached `web/legacy-demo.html` is the independent browser UI V0.6, maintained as a reference, not used as a security boundary.

## Run locally

Requires Python 3.10+ with FastAPI, Pydantic and Uvicorn.

Windows PowerShell:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\RUN_WINDOWS.ps1
```

Then visit http://127.0.0.1:8766/. Demo account: `demo.admin` / `FairProof2026!` **only with synthetic demo mode enabled**. Do **not** expose the demo password or the demo server publicly. `RUN_WINDOWS.ps1` binds to 127.0.0.1 deliberately.

Other systems:

```bash
python -m pip install -e '.[test]' -r requirements-app.txt
CANICOMMERCE_DEMO_MODE=1 python -m uvicorn app:app --host 127.0.0.1 --port 8766
```

`CANICOMMERCE_DB` overrides the default local SQLite path. You can use `CANICOMMERCE_DEMO_USER` and `CANICOMMERCE_DEMO_PASSWORD` to supply separate local demo credentials (only before the first launch). Without `CANICOMMERCE_DEMO_MODE=1`, no default operator is provisioned.

## Functional integration

- Server-checked demo admin login, password hash and expiring bearer session (in-memory, non-production).
- Synthetic order creation; eligible MYR product amount, original agent, optional selling partner; **no phantom seller on direct sales**.
- Frozen commission policy version on every order; new changes are forward-only, with authenticated actor, reason and before/after audit.
- 28-day commission eligibility from capture timestamp. **No payout system is implemented.**
- Order amendments append signed adjustment/reversal rows. Historical commission captures remain intact. Dispute action blocks eligibility conceptually, but no real settlement scheduler exists.
- SQLite audit event hash linkage; local verification endpoint (hash chains are not tamper-proof against privileged DB rewrite).
- Independent locally computed Merkle proof for **current** synthetic data, flagged **NOT ANCHORED**.
- Reuse of original Sepolia Merkle proof and anchor manifest; the already deployed original contract/transaction is never mutated.

## Mandatory production gates (NOT COMPLETE)

- Enterprise-grade identity provider, MFA, server-side RBAC/row policies, replay protection, rate-limited login, session revocation, CSRF/browser security review.
- Transactional payment-provider capture verification and signed webhook handling.
- PostgreSQL migration, migrations, idempotency and locking across concurrent workers, multi-tenant isolation and backup/recovery.
- Refund/dispute reconciliation, 28-day batch settlement approvals, actual transfers and payout reporting.
- Publisher wallet policy with human approval, confirmed fresh Merkle root, chain receipt and finality checks.
- Permanent audit storage/WORM or independent anchor; immutable evidence and external verification.
- Security review, privacy and licensing review, operator runbook, and consent/retention safeguards.

**No deployment to main, no live payments, no CAIOS private data, and no new Ethereum transactions.**