-- Cover foreign-key lookup paths reported by Supabase's performance advisor.
-- Idempotent so it can be safely re-applied in disposable/staging environments.
CREATE INDEX IF NOT EXISTS analyses_run_id_idx
  ON bharatsim.analyses (run_id);
CREATE INDEX IF NOT EXISTS artifacts_owner_id_idx
  ON bharatsim.artifacts (owner_id);
CREATE INDEX IF NOT EXISTS workers_current_run_id_idx
  ON bharatsim.workers (current_run_id);
