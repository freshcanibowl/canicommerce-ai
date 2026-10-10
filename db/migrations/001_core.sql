-- DRAFT ONLY: no migration has been executed.
CREATE TABLE partners (
  id uuid PRIMARY KEY,
  partner_type text NOT NULL CHECK (partner_type IN ('AGENT','SHOP','VET','GROOMER','KOL','OTHER')),
  status text NOT NULL CHECK (status IN ('ACTIVE','SUSPENDED')),
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE customers (
  id uuid PRIMARY KEY,
  consent_status text NOT NULL DEFAULT 'UNKNOWN',
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE customer_attributions (
  id uuid PRIMARY KEY,
  customer_id uuid NOT NULL REFERENCES customers(id),
  original_agent_id uuid NOT NULL REFERENCES partners(id),
  effective_at timestamptz NOT NULL,
  corrected_at timestamptz,
  correction_reason text,
  supersedes_id uuid REFERENCES customer_attributions(id)
);
CREATE TABLE orders (
  id uuid PRIMARY KEY,
  customer_id uuid NOT NULL REFERENCES customers(id),
  selling_partner_id uuid REFERENCES partners(id),
  eligible_net_sen bigint NOT NULL CHECK (eligible_net_sen >= 0),
  currency char(3) NOT NULL DEFAULT 'MYR',
  status text NOT NULL CHECK (status IN ('PENDING','CAPTURED','REFUNDED','PARTIALLY_REFUNDED','DISPUTED')),
  captured_at timestamptz
);
CREATE TABLE payment_events (
  id uuid PRIMARY KEY,
  provider text NOT NULL,
  provider_event_id text NOT NULL,
  order_id uuid REFERENCES orders(id),
  verified_at timestamptz,
  payload_hash text NOT NULL,
  UNIQUE(provider,provider_event_id)
);
CREATE TABLE commission_entries (
  id uuid PRIMARY KEY,
  order_id uuid NOT NULL REFERENCES orders(id),
  partner_id uuid NOT NULL REFERENCES partners(id),
  entry_type text NOT NULL CHECK (entry_type IN ('ORIGINAL','SELLER','REVERSAL')),
  amount_sen bigint NOT NULL,
  business_key text NOT NULL UNIQUE,
  eligible_at timestamptz NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE settlement_batches (
  id uuid PRIMARY KEY,
  status text NOT NULL CHECK (status IN ('DRAFT','APPROVED','PAID','CANCELLED')),
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE settlement_items (
  batch_id uuid NOT NULL REFERENCES settlement_batches(id),
  commission_entry_id uuid NOT NULL UNIQUE REFERENCES commission_entries(id),
  PRIMARY KEY(batch_id,commission_entry_id)
);
CREATE TABLE audit_events (
  id uuid PRIMARY KEY,
  actor_id text NOT NULL,
  action text NOT NULL,
  entity_type text NOT NULL,
  entity_id text NOT NULL,
  reason text,
  occurred_at timestamptz NOT NULL DEFAULT now()
);
-- TODO before production: RLS, append-only DB permissions, settlement locking,
-- verified webhook transaction, immutable attribution history, reversal reconciliation.
