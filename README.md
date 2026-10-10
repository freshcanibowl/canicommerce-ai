# CaniCommerce AI — Build 0 + Build 1

Isolated, deterministic commission prototype. No live payments, production credentials, CAIOS integration, or Web3 dependencies.

## Scope
- Original referring agent: 3% of eligible net product sales
- Selling partner: 7% of eligible net product sales
- Same partner can earn both; no multilevel commissions
- 28-day eligibility after capture; disputed orders blocked
- Refund reversals are append-only; demo ledger deduplicates business keys
- PostgreSQL migration is a **draft**, not a deployed schema

## Local test
```bash
python -m pip install -e '.[test]'
python -m pytest -q
```

**Production blockers:** authenticated customer/partner access, DB-backed transactional idempotency, payment signature verification, settlement payout/reconciliation, dispute lifecycle, consent and retention rules.

This repository was created independently. No changes to CAIOS main, CaniPay, CaniCircle, or CaniBowl Journey.
