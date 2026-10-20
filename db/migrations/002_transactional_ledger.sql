-- Build 1.1 draft: run in a dedicated test database only after review.
-- Database role for the application must not own these tables or have UPDATE/DELETE on ledger rows.
CREATE TABLE IF NOT EXISTS processed_payment_events (
  provider text NOT NULL,
  provider_event_id text NOT NULL,
  order_id uuid NOT NULL REFERENCES orders(id),
  payload_hash text NOT NULL,
  processed_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY(provider, provider_event_id)
);
CREATE TABLE IF NOT EXISTS order_commission_state (
  order_id uuid PRIMARY KEY REFERENCES orders(id),
  captured_eligible_sen bigint NOT NULL CHECK (captured_eligible_sen >= 0),
  cumulative_refunded_sen bigint NOT NULL DEFAULT 0 CHECK (cumulative_refunded_sen >= 0),
  CHECK (cumulative_refunded_sen <= captured_eligible_sen)
);
CREATE TABLE IF NOT EXISTS settlement_locks (
  order_id uuid PRIMARY KEY REFERENCES orders(id),
  batch_id uuid NOT NULL REFERENCES settlement_batches(id),
  locked_at timestamptz NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX IF NOT EXISTS customer_attributions_one_active
  ON customer_attributions(customer_id) WHERE corrected_at IS NULL;
CREATE INDEX IF NOT EXISTS commission_entries_eligible_idx
  ON commission_entries(eligible_at, order_id);
-- Block UPDATE and DELETE at database layer; append-only means insert + compensating reversal.
CREATE OR REPLACE FUNCTION forbid_commission_mutation() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN RAISE EXCEPTION 'commission_entries are append-only'; END;
$$;
DROP TRIGGER IF EXISTS commission_entries_immutable ON commission_entries;
CREATE TRIGGER commission_entries_immutable BEFORE UPDATE OR DELETE ON commission_entries
FOR EACH ROW EXECUTE FUNCTION forbid_commission_mutation();
-- TODO: verified webhook signatures, database roles/RLS, batch payout and compensation.
