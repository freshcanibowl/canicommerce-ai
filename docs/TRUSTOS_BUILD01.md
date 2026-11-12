# TrustOS Build 01 — Payment Contract (synthetic-only)

This isolated branch adds `payment_contract.py` and negative fixture tests. It does **not** connect to PayPal, execute Capture, verify OAuth/webhook signatures, or authorize commission posting. **Do not treat `UNAUTHENTICATED_PAYLOAD_PARSED` as a verified provider receipt.**

## Run locally
```powershell
python -m pip install -e '.[test]'
python -m pytest -q
```

## Integration boundary
1. Obtain PayPal sandbox OAuth through a server-side secret store.
2. GET the order and capture from PayPal via authenticated TLS. Validate merchant/payee ownership and trusted order binding separately.
3. Only then parse and compare capture fields to server-side expected currency and integer minor units.
4. Capture evidence must be signed or independently fetched and reconciled; browser redirect and JSON fixtures are untrusted.
5. A **future** provider verifier must issue a distinct authenticated receipt type before the ledger can post credits.
6. Keep `core.py` existing 3%/7% calculation isolated from USD until explicit currency-aware ledger migration. The existing `amount_sen` naming is MYR-specific and cannot safely represent arbitrary PayPal currencies.

## GO/NO-GO
| Why continue | Stop / kill |
| --- | --- |
| Existing deterministic commission core is reusable | Currency ambiguity or merchant identity cannot be resolved |
| Offline capture parser can reject invalid values | Any unauthenticated payload causes ledger credit |
| Tests do not require secrets | A live endpoint or money-moving tool is added to this branch |

**Status:** proposed contract with synthetic fixtures; not production-verified. Next: sandbox read-only provider verifier and authenticated merchant binding, then durable event inbox.
