-- Trusted PayPal provider-order mapping; never infer local order from webhook data.
CREATE TABLE provider_order_mappings (
  id uuid PRIMARY KEY,
  provider text NOT NULL CHECK (provider='paypal-sandbox'),
  provider_order_id text NOT NULL,
  local_order_id uuid NOT NULL REFERENCES orders(id),
  expected_merchant_id text NOT NULL,
  expected_gross_sen bigint NOT NULL CHECK(expected_gross_sen>0),
  currency char(3) NOT NULL DEFAULT 'MYR' CHECK(currency='MYR'),
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE(provider,provider_order_id),
  UNIQUE(provider,local_order_id)
);
CREATE TRIGGER provider_order_mappings_immutable
BEFORE UPDATE OR DELETE ON provider_order_mappings
FOR EACH ROW EXECUTE FUNCTION forbid_financial_row_mutation();

CREATE TABLE provider_capture_mappings (
  id uuid PRIMARY KEY,
  provider text NOT NULL CHECK(provider='paypal-sandbox'),
  provider_capture_id text NOT NULL,
  provider_order_id text NOT NULL,
  local_order_id uuid NOT NULL REFERENCES orders(id),
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE(provider,provider_capture_id),
  UNIQUE(provider,local_order_id),
  FOREIGN KEY(provider,provider_order_id)
    REFERENCES provider_order_mappings(provider,provider_order_id)
);
CREATE TRIGGER provider_capture_mappings_immutable
BEFORE UPDATE OR DELETE ON provider_capture_mappings
FOR EACH ROW EXECUTE FUNCTION forbid_financial_row_mutation();
