-- Explicit trusted-server policy plus indexes for foreign-key access paths.
-- Browser roles still have no schema/table grants and the schema is not Data API exposed.
CREATE INDEX IF NOT EXISTS analyses_run_id_idx ON bharatsim.analyses (run_id);
CREATE INDEX IF NOT EXISTS artifacts_owner_id_idx ON bharatsim.artifacts (owner_id);
CREATE INDEX IF NOT EXISTS workers_current_run_id_idx ON bharatsim.workers (current_run_id);

DROP POLICY IF EXISTS bharatsim_service_role_access ON bharatsim.runs;
CREATE POLICY bharatsim_service_role_access ON bharatsim.runs
    TO service_role USING (true) WITH CHECK (true);
DROP POLICY IF EXISTS bharatsim_service_role_access ON bharatsim.analyses;
CREATE POLICY bharatsim_service_role_access ON bharatsim.analyses
    TO service_role USING (true) WITH CHECK (true);
DROP POLICY IF EXISTS bharatsim_service_role_access ON bharatsim.workers;
CREATE POLICY bharatsim_service_role_access ON bharatsim.workers
    TO service_role USING (true) WITH CHECK (true);
DROP POLICY IF EXISTS bharatsim_service_role_access ON bharatsim.run_events;
CREATE POLICY bharatsim_service_role_access ON bharatsim.run_events
    TO service_role USING (true) WITH CHECK (true);
DROP POLICY IF EXISTS bharatsim_service_role_access ON bharatsim.artifacts;
CREATE POLICY bharatsim_service_role_access ON bharatsim.artifacts
    TO service_role USING (true) WITH CHECK (true);
DROP POLICY IF EXISTS bharatsim_service_role_access ON bharatsim.quotas;
CREATE POLICY bharatsim_service_role_access ON bharatsim.quotas
    TO service_role USING (true) WITH CHECK (true);
DROP POLICY IF EXISTS bharatsim_service_role_access ON bharatsim.audit_events;
CREATE POLICY bharatsim_service_role_access ON bharatsim.audit_events
    TO service_role USING (true) WITH CHECK (true);
