-- Build 1.2 hardening: append-only enforcement for payment events and attribution audit.
-- Apply ONLY to a disposable PostgreSQL test database, after 001 and 002.
CREATE OR REPLACE FUNCTION forbid_financial_row_mutation() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN RAISE EXCEPTION 'financial audit rows are immutable'; END;
$$;
DROP TRIGGER IF EXISTS processed_payment_events_immutable ON processed_payment_events;
CREATE TRIGGER processed_payment_events_immutable
BEFORE UPDATE OR DELETE ON processed_payment_events
FOR EACH ROW EXECUTE FUNCTION forbid_financial_row_mutation();
DROP TRIGGER IF EXISTS payment_events_immutable ON payment_events;
CREATE TRIGGER payment_events_immutable
BEFORE UPDATE OR DELETE ON payment_events
FOR EACH ROW EXECUTE FUNCTION forbid_financial_row_mutation();

-- Capture must be idempotent per order, not merely per provider event.
CREATE UNIQUE INDEX IF NOT EXISTS one_original_commission_per_order
  ON commission_entries(order_id) WHERE entry_type='ORIGINAL';
CREATE UNIQUE INDEX IF NOT EXISTS one_seller_commission_per_order
  ON commission_entries(order_id) WHERE entry_type='SELLER';

-- A settled item must have an auditable payout/recovery state in the future.
-- This migration does NOT implement payment gateway verification, RLS or payouts.
