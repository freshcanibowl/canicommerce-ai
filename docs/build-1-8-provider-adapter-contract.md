# Build 1.8 — provider verification boundary

The `VerifiedCapture` type is an **internal validated claim**, not proof
that a payment gateway was called. The `provider_signature_verified` and
`provider_capture_confirmed` flags are trusted ONLY if a server-side adapter
sets them after independently checking the provider.

## Required PayPal Sandbox adapter (NOT YET IMPLEMENTED)
1. Receive webhook on an authenticated server endpoint; enforce body-size limits.
2. Verify PayPal webhook signature using official API/SDK, configured webhook ID,
   transmission ID/time/signature/cert URL and raw body; reject failures.
3. Independently GET capture details from PayPal using server credentials.
4. Confirm capture status COMPLETED, capture ID, currency, amount, merchant,
   expected local order mapping and permitted capture transitions.
5. Calculate eligible product net from trusted local order lines; exclude
   shipping, tax, refunds, and disallowed items. Never trust eligible net from
   the webhook.
6. Atomically write verified event + capture + commissions via repository,
   with idempotency and full amount reconciliation.
7. Secure secrets in CI/deployment vault; log only redacted event metadata.

## Still blocked
- No PayPal adapter or actual webhook signature verification.
- The new boundary function is NOT wired to `PostgresCommissionRepository.capture`.
- No webhook endpoint, provider credentials, payout integration, RBAC or RLS.
- No production deployment or money movement.

Do not mark this as PayPal integration complete.
