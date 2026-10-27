-- Defense-in-depth for the private BharatSim namespace.
-- The schema remains absent from the Supabase Data API exposed schemas.
-- Browser roles receive explicit deny policies even if grants are accidentally added later.
-- This migration does not touch GenomeGuard objects.

CREATE INDEX IF NOT EXISTS analyses_run_id_idx
    ON bharatsim.analyses (run_id);
CREATE INDEX IF NOT EXISTS artifacts_owner_id_idx
    ON bharatsim.artifacts (owner_id);
CREATE INDEX IF NOT EXISTS workers_current_run_id_idx
    ON bharatsim.workers (current_run_id);

DROP POLICY IF EXISTS deny_client_access_runs ON bharatsim.runs;
CREATE POLICY deny_client_access_runs
    ON bharatsim.runs FOR ALL TO anon, authenticated
    USING (false) WITH CHECK (false);

DROP POLICY IF EXISTS deny_client_access_analyses ON bharatsim.analyses;
CREATE POLICY deny_client_access_analyses
    ON bharatsim.analyses FOR ALL TO anon, authenticated
    USING (false) WITH CHECK (false);

DROP POLICY IF EXISTS deny_client_access_workers ON bharatsim.workers;
CREATE POLICY deny_client_access_workers
    ON bharatsim.workers FOR ALL TO anon, authenticated
    USING (false) WITH CHECK (false);

DROP POLICY IF EXISTS deny_client_access_run_events ON bharatsim.run_events;
CREATE POLICY deny_client_access_run_events
    ON bharatsim.run_events FOR ALL TO anon, authenticated
    USING (false) WITH CHECK (false);

DROP POLICY IF EXISTS deny_client_access_artifacts ON bharatsim.artifacts;
CREATE POLICY deny_client_access_artifacts
    ON bharatsim.artifacts FOR ALL TO anon, authenticated
    USING (false) WITH CHECK (false);

DROP POLICY IF EXISTS deny_client_access_quotas ON bharatsim.quotas;
CREATE POLICY deny_client_access_quotas
    ON bharatsim.quotas FOR ALL TO anon, authenticated
    USING (false) WITH CHECK (false);

DROP POLICY IF EXISTS deny_client_access_audit_events ON bharatsim.audit_events;
CREATE POLICY deny_client_access_audit_events
    ON bharatsim.audit_events FOR ALL TO anon, authenticated
    USING (false) WITH CHECK (false);
