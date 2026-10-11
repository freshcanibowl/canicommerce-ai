-- SECURITY DRAFT: Run only in a dedicated disposable database as an admin.
-- Never run this script on production without owner review and role migration plan.
-- The webhook edge does not require any direct table access.
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='canicommerce_edge') THEN
    CREATE ROLE canicommerce_edge NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION;
  END IF;
END $$;
REVOKE ALL ON SCHEMA public FROM canicommerce_edge;
REVOKE ALL ON ALL TABLES IN SCHEMA public FROM canicommerce_edge;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM canicommerce_edge;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA public FROM canicommerce_edge;
-- PostgreSQL grants EXECUTE on new functions to PUBLIC by default.
-- Remove this ambient access for future functions in this schema.
ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE EXECUTE ON FUNCTIONS FROM PUBLIC;
-- No CREATE, no USAGE, no SELECT, no INSERT, no UPDATE, no DELETE.
-- Only a separate, server-owned privileged worker may perform verified capture.
