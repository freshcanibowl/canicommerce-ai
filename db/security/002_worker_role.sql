-- DRAFT: disposable dedicated PostgreSQL only, applied by schema owner.
-- No login/password, no table ownership, no superuser or role creation.
-- Not a production migration. Verify complete operational privilege matrix first.
DO $$
BEGIN
 IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='canicommerce_worker') THEN
   CREATE ROLE canicommerce_worker NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION;
 END IF;
END $$;
GRANT USAGE ON SCHEMA public TO canicommerce_worker;
GRANT SELECT ON TABLE
  public.orders,public.customers,public.partners,public.customer_attributions,
  public.provider_order_mappings,public.provider_capture_mappings,
  public.processed_payment_events,public.order_commission_state,
  public.commission_entries
TO canicommerce_worker;
GRANT UPDATE (status,captured_at) ON public.orders TO canicommerce_worker;
GRANT INSERT ON TABLE
  public.provider_capture_mappings,public.processed_payment_events,
  public.order_commission_state,public.commission_entries
TO canicommerce_worker;
-- Deliberately NO access to settlement approvals, payouts, audit modification,
-- provider order registration, attribution modification, refund/recovery.
-- Worker can only be used behind server-owned verified PayPal capture ingress.
-- DB grants alone do NOT attest to PayPal verification; isolation is mandatory.
