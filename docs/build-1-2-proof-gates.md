# Build 1.2 PostgreSQL proof gates

CI tests a disposable PostgreSQL 16 service only. It never contacts a production database.

Included:
- 001, 002 and 003 migrations applied to disposable DB
- append-only triggers for commission and processed payment events
- unique capture commission per order/type
- concurrent duplicate event INSERT race
- cumulative refund bound check
- one settlement lock per order

Not yet proven:
- Full capture transaction across payment event, order, attribution and commissions
- Concurrent refund vs settlement in one atomic transaction
- Signed PayPal webhook verification and exact provider payload reconciliation
- Post-settlement recovery ledger
- Tenant RLS, production auth, payout authorization, database least-privilege

Never merge or deploy migrations until reviewed and tested.
