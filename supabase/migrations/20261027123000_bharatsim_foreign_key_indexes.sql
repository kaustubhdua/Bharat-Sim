-- Cover foreign-key lookups reported by the Supabase performance advisor.
-- This migration is scoped exclusively to BharatSim's private schema.
-- It does not alter the pre-existing GenomeGuard schema.
CREATE INDEX IF NOT EXISTS analyses_run_id_idx
    ON bharatsim.analyses (run_id)
    WHERE run_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS artifacts_owner_id_idx
    ON bharatsim.artifacts (owner_id)
    WHERE owner_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS workers_current_run_id_idx
    ON bharatsim.workers (current_run_id)
    WHERE current_run_id IS NOT NULL;
