# TrustOS Build 02 — Read-only PayPal Sandbox verifier

## Scope and status
**Source implemented on isolated branch; tests not independently executed in CI or local environment yet.** No live network was contacted. No PayPal Capture, refund or payout POST endpoints are present. All test data are synthetic. This does not prove that a historical order was paid.

Build 01 contract parses capture fields but marks them `UNAUTHENTICATED_PAYLOAD_PARSED`. Build 02 introduces an authenticated sandbox OAuth + order GET + capture GET verification path and only returns `PROVIDER_READBACK_SANDBOX` after all checks. This is a code-path label, **not a claim that a real provider readback occurred in this repository**.

## Read-only validation gates
- Sandbox host is constant: `https://api-m.sandbox.paypal.com`; the transport permits POST only for OAuth `/v1/oauth2/token`, GET for provider resources.
- Order and capture IDs are restricted to safe ASCII provider ID characters; no user-supplied URLs.
- Server-held expected order, merchant, currency and amount must be independent of the returned payload and browser redirects.
- Order status `COMPLETED`; exactly one purchase unit, one embedded capture, expected `payee.merchant_id`.
- Embedded capture status `COMPLETED`; independent capture GET status `COMPLETED`; matching capture ID and amount/currency; related order checked when provider includes it.
- Any missing or ambiguous field fails closed. No commission ledger writes occur.

## Local test (no secrets)
```powershell
git checkout build/trustos-sandbox-readonly-02
python -m pip install -e '.[test]'
python -m pytest -q
```

## Optional read-only Sandbox validation
Run **only** with a PayPal Sandbox Business app whose merchant ID matches the order's payee. Never paste secrets into chat or commit them. Before using the CLI below, validate the merchant ID independently in the PayPal developer dashboard. Use a unique expected order/amount; the previous USD 1.00 Sandbox order is not presumed captured.

```powershell
$env:PAYPAL_MODE='sandbox'
$env:PAYPAL_CLIENT_ID=Read-Host 'Sandbox Client ID'
$env:PAYPAL_CLIENT_SECRET=Read-Host 'Sandbox Secret' -MaskInput
$env:PAYPAL_MERCHANT_ID=Read-Host 'Expected Sandbox merchant ID'
python -m canicommerce.readonly_check --order-id 42F30363NC237835G --amount-minor 100 --currency USD
Remove-Item Env:PAYPAL_CLIENT_ID,Env:PAYPAL_CLIENT_SECRET,Env:PAYPAL_MERCHANT_ID -ErrorAction SilentlyContinue
```

The CLI only prints redacted receipt identifiers and gate verdicts; it never prints credentials or access tokens. **If order is CREATED or APPROVED but not COMPLETED, the check must fail.** It never performs capture.

## Known limitations / NO-GO
- No webhook signature validation or durable provider-event inbox.
- No persistent idempotency store or atomic ledger writes.
- Only one purchase unit and one capture; complex orders explicitly unsupported.
- No production entitlement, payer authorization, jurisdiction compliance or payout permission review.
- Readback verification depends on TLS trust and provider API, and does not provide an independently signed receipt.
- Current core uses MYR-specific `amount_sen`; USD receipt must **not** be passed to it until currency-aware ledger is implemented.
- GitHub-hosted code has not been validated by an independent runner.

**GO** for synthetic unit testing and sandbox GET verification; **NO-GO** for ledger credit, live transactions or automatic payouts.
