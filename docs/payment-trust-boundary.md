# CaniCommerce AI — Payment Trust Boundary (Build 2.9)

Status: **Sandbox-only, NOT production-ready**. This document defines release gates, not a security certification.

## Threat model
Untrusted: incoming HTTP requests, webhook headers/body, event IDs, PayPal order IDs carried in a webhook, caller-created Python dataclasses, browser state and any request-provided customer, commission or order values.

Trusted only after independently established: server-owned PayPal Sandbox credentials; successful PayPal webhook-signature verification; fresh PayPal Capture GET confirming COMPLETED, MYR, merchant, order and amount; immutable server-created order mapping; transactionally checked local order/customer/eligible net.

## Required call graph

Public HTTPS edge (not implemented)
  -> size, method, rate and content-type limits (not implemented)
  -> process_trusted_paypal_sandbox_webhook (server credentials only)
  -> process_paypal_capture_webhook (routing hint is NOT authority)
  -> PayPalSandboxAdapter.verify_capture (remote verification)
  -> capture_verified (internal-only DB transaction)
  -> commission entries (3% original agent, 7% selling partner)

## Critical restriction

`VerifiedCapture` is a regular dataclass and can be forged by Python code. `capture_verified`, `PostgresCommissionRepository.capture` and the underlying database are **privileged internal interfaces**, NOT safe public endpoints. Never accept a caller-supplied `VerifiedCapture` or booleans claiming a signature was verified. Do not grant a web-edge DB role direct INSERT permissions to `orders`, `processed_payment_events`, `provider_capture_mappings`, `commission_entries` or `settlement_batches`.

The present Python package does **not** cryptographically authenticate its own internal calls. Security depends on isolating internal modules, database credentials and network access. Before production, implement and verify role-level database least privilege and a single server-owned verified-capture posting path. A test fake adapter must never be enabled in a deployed runtime.

## Sandbox verification checklist

- [ ] Configure Sandbox-only credentials as protected server secrets, never GitHub source or chat
- [ ] Confirm OAuth and webhook-signature verification against PayPal Sandbox
- [ ] Confirm Capture GET reconciliation: ID, COMPLETED, MYR, merchant, gross, PayPal order ID
- [ ] Reject tampered body, forged headers, wrong merchant and wrong amount
- [ ] Verify replay and concurrent delivery post exactly one commission set
- [ ] Implement an HTTPS webhook edge with body-size, rate limits and safe error responses
- [ ] Verify TLS, no redirects, no token leakage and log redaction
- [ ] Enforce DB least privilege, prohibit edge-side direct ledger writes
- [ ] Verify no automatic payout, no production credentials, no live payments
- [ ] Security review and explicit owner approval before any production rollout

## Non-goals

No production deployment, live PayPal API, automated payouts, main merge, CAIOS or CaniPay modifications. Refund/recovery requires its own independently verified provider refund boundary.
