-- Build 4.0: protect governance audit history against in-place mutation.
-- Only apply in an isolated disposable PostgreSQL test database.
-- Existing audit events remain readable; corrections must be new events.
DROP TRIGGER IF EXISTS audit_events_immutable ON audit_events;
CREATE TRIGGER audit_events_immutable
BEFORE UPDATE OR DELETE ON audit_events
FOR EACH ROW EXECUTE FUNCTION forbid_financial_row_mutation();

-- Settlement batches and items require authorized state transitions and cannot
-- be declared append-only until an explicit state-machine/approval design ships.
-- Do not grant the capture worker any privileges on audit_events.
