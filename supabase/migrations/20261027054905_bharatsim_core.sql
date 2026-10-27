-- BharatSim-only persistence namespace. This migration must never alter GenomeGuard objects.
-- The schema is intentionally not exposed through Supabase's Data API.
CREATE SCHEMA IF NOT EXISTS bharatsim;

REVOKE ALL ON SCHEMA bharatsim FROM PUBLIC, anon, authenticated;
GRANT USAGE ON SCHEMA bharatsim TO service_role;

CREATE TABLE IF NOT EXISTS bharatsim.runs (
    id text PRIMARY KEY,
    owner_id uuid NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    created_at text NOT NULL,
    updated_at text NOT NULL,
    status text NOT NULL CHECK (status IN ('awaiting_worker','queued','leased','running','completed','failed','cancelled')),
    apk_name text,
    apk_sha256 text CHECK (apk_sha256 IS NULL OR apk_sha256 ~ '^[0-9a-f]{64}$'),
    apk_path text,
    apk_storage_path text,
    persona_id text NOT NULL,
    result_json text,
    error text,
    lease_token text,
    lease_until text,
    worker_id text,
    attempts integer NOT NULL DEFAULT 0 CHECK (attempts >= 0),
    idempotency_key text,
    CHECK (status <> 'completed' OR result_json IS NOT NULL)
);
CREATE INDEX IF NOT EXISTS runs_status_created_idx ON bharatsim.runs (status, created_at);
CREATE INDEX IF NOT EXISTS runs_owner_created_idx ON bharatsim.runs (owner_id, created_at DESC);
CREATE UNIQUE INDEX IF NOT EXISTS runs_owner_idempotency_idx
    ON bharatsim.runs (owner_id, idempotency_key)
    WHERE owner_id IS NOT NULL AND idempotency_key IS NOT NULL;

CREATE TABLE IF NOT EXISTS bharatsim.analyses (
    id text PRIMARY KEY,
    owner_id uuid NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    created_at text NOT NULL,
    run_id text NULL REFERENCES bharatsim.runs(id) ON DELETE SET NULL,
    persona_id text NOT NULL,
    result_json text NOT NULL
);
CREATE INDEX IF NOT EXISTS analyses_owner_created_idx ON bharatsim.analyses (owner_id, created_at DESC);

CREATE TABLE IF NOT EXISTS bharatsim.workers (
    id text PRIMARY KEY,
    last_seen text NOT NULL,
    status text NOT NULL CHECK (status IN ('idle','running','offline')),
    current_run_id text NULL REFERENCES bharatsim.runs(id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS workers_last_seen_idx ON bharatsim.workers (last_seen DESC);

CREATE TABLE IF NOT EXISTS bharatsim.run_events (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    run_id text NOT NULL REFERENCES bharatsim.runs(id) ON DELETE CASCADE,
    event_type text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    actor_type text NOT NULL CHECK (actor_type IN ('user','worker','system')),
    actor_id text,
    payload_json text NOT NULL DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS run_events_run_created_idx ON bharatsim.run_events (run_id, created_at);

CREATE TABLE IF NOT EXISTS bharatsim.artifacts (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id text NOT NULL REFERENCES bharatsim.runs(id) ON DELETE CASCADE,
    owner_id uuid NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    object_path text NOT NULL UNIQUE,
    artifact_kind text NOT NULL CHECK (artifact_kind IN ('apk','logcat','screenshot','report','appium','other')),
    content_type text NOT NULL,
    byte_size bigint NOT NULL CHECK (byte_size >= 0),
    sha256 text NOT NULL CHECK (sha256 ~ '^[0-9a-f]{64}$'),
    created_at timestamptz NOT NULL DEFAULT now(),
    expires_at timestamptz,
    deleted_at timestamptz
);
CREATE INDEX IF NOT EXISTS artifacts_run_idx ON bharatsim.artifacts (run_id);
CREATE INDEX IF NOT EXISTS artifacts_expiry_idx ON bharatsim.artifacts (expires_at) WHERE deleted_at IS NULL;

CREATE TABLE IF NOT EXISTS bharatsim.quotas (
    owner_id uuid PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    daily_run_limit integer NOT NULL DEFAULT 10 CHECK (daily_run_limit > 0),
    active_run_limit integer NOT NULL DEFAULT 2 CHECK (active_run_limit > 0),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS bharatsim.audit_events (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    owner_id uuid NULL REFERENCES auth.users(id) ON DELETE SET NULL,
    actor_type text NOT NULL CHECK (actor_type IN ('user','worker','system','admin')),
    actor_id text,
    action text NOT NULL,
    resource_type text NOT NULL,
    resource_id text,
    created_at timestamptz NOT NULL DEFAULT now(),
    metadata_json text NOT NULL DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS audit_events_owner_created_idx ON bharatsim.audit_events (owner_id, created_at DESC);

-- RLS is enabled as defense in depth. No client policies are created; browser roles
-- have no schema/table grants. The trusted server-side service role is the only
-- Supabase API role granted table access. User ownership must still be enforced
-- by the API before this schema is used for customer data.
ALTER TABLE bharatsim.runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE bharatsim.analyses ENABLE ROW LEVEL SECURITY;
ALTER TABLE bharatsim.workers ENABLE ROW LEVEL SECURITY;
ALTER TABLE bharatsim.run_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE bharatsim.artifacts ENABLE ROW LEVEL SECURITY;
ALTER TABLE bharatsim.quotas ENABLE ROW LEVEL SECURITY;
ALTER TABLE bharatsim.audit_events ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON ALL TABLES IN SCHEMA bharatsim FROM PUBLIC, anon, authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA bharatsim TO service_role;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA bharatsim TO service_role;
ALTER DEFAULT PRIVILEGES IN SCHEMA bharatsim REVOKE ALL ON TABLES FROM PUBLIC, anon, authenticated;
ALTER DEFAULT PRIVILEGES IN SCHEMA bharatsim GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO service_role;
ALTER DEFAULT PRIVILEGES IN SCHEMA bharatsim GRANT USAGE, SELECT ON SEQUENCES TO service_role;
