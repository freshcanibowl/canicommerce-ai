-- Build 1.6: immutable recovery obligation journal.
-- Apply to disposable CI PostgreSQL only.
CREATE TABLE recovery_obligations (
  id uuid PRIMARY KEY,
  order_id uuid NOT NULL REFERENCES orders(id),
  partner_id uuid NOT NULL REFERENCES partners(id),
  provider text NOT NULL,
  provider_event_id text NOT NULL,
  amount_sen bigint NOT NULL CHECK (amount_sen > 0),
  currency char(3) NOT NULL DEFAULT 'MYR',
  reason text NOT NULL CHECK (reason IN ('POST_APPROVAL_REFUND','POST_PAYOUT_REFUND')),
  occurred_at timestamptz NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE(provider,provider_event_id,partner_id)
);
CREATE TRIGGER recovery_obligations_immutable
BEFORE UPDATE OR DELETE ON recovery_obligations
FOR EACH ROW EXECUTE FUNCTION forbid_financial_row_mutation();

-- Recovery payments/offsets are NOT implemented. Obligations are not payouts.
