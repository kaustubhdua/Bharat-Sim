# Supabase persistence for BharatSim

## Scope and data boundary

BharatSim uses the Supabase project **common 1** (ref hkyieaovolkethovyenb, ap-south-1) as its planned PostgreSQL persistence target. That project already contains GenomeGuard objects. The migration in this repository creates only the separate bharatsim schema and does not rename, drop, or modify any genomeguard object.

The bharatsim schema is deliberately excluded from Supabase Data API exposure in supabase/config.toml. Its tables have RLS enabled; anon and authenticated receive no schema/table grants, and the server-side service_role is the only Supabase API role granted table access. Never place a service-role key in the browser or a VITE_* variable.

## Migration

The versioned schema migration is:

- `supabase/migrations/20261027110000_bharatsim_core.sql`
- `supabase/migrations/20261027060000_harden_bharatsim_rls_and_indexes.sql` (applies after the core migration in version order; see note below)

It creates the durable run, analysis, worker, event, artifact, quota, and audit tables plus indexes and integrity constraints. The follow-up hardening migration adds explicit deny-all RLS policies for `anon` and `authenticated` on all seven tables and indexes the three foreign-key columns flagged by the live performance advisor. Both migrations are additive and scoped to `bharatsim`; they do not create or modify Storage buckets, change Auth settings, alter GenomeGuard security, or enable public client access. Keep migration filenames in ascending timestamp order; the hardening migration must run after the core migration.

Apply the reviewed migration to the intended Supabase project through the Supabase migration workflow, then verify the resulting bharatsim tables and run both Supabase security and performance advisors. Do not apply it to a different project by accident.

## Backend connection

Local development continues to use SQLite unless BHARATSIM_DATABASE_URL is set. To opt into the Supabase PostgreSQL path:

1. Apply the reviewed migration first.
2. Set BHARATSIM_DATABASE_URL in the **server environment only** to a TLS-enabled PostgreSQL connection string for the intended project.
3. Use a dedicated least-privilege database login and a connection pooler where appropriate. Do not use the database-owner credential for a public service.
4. Start the API. If the URL is set but bharatsim.runs is missing, startup fails instead of creating or silently mutating a production schema.
5. Verify /health/ready, API persistence tests, worker claim/lease/result tests, and restart durability before switching traffic.

The compatibility adapter translates existing parameterized SQLite-style placeholders for PostgreSQL. The current API's SQL operations are adapted to the isolated schema, but **this is not yet a production multi-tenant release**.

## Explicit blockers before public customer data

- API routes still need verified Supabase Auth JWT validation and per-user ownership checks for runs, analyses, cancellation and artifacts.
- owner_id is nullable to preserve compatibility with the current unauthenticated local MVP; the API must not claim cross-user isolation until ownership is mandatory for customer-facing records and deny tests pass.
- The database connection role must be least-privileged; never expose the service-role key.
- Private Storage buckets, short-lived signed URLs, upload size/type enforcement at the storage boundary, hash verification, retention and deletion are not implemented by this migration.
- Worker isolation, default-deny egress, quotas, physical-device validation, public deployment verification and backup/restore drills remain separate release gates.
- The SQLite path remains available for local development and tests. A real production migration still requires a tested data migration and rollback plan.

## Verification checklist

- [x] Apply the core and hardening migrations to the intended `common 1` project and verify the seven expected tables in the `bharatsim` schema.
- [x] Confirm `bharatsim` is not in the project's exposed Data API schemas (`supabase/config.toml` exposes only `public` and `graphql_public`).
- [x] Confirm `anon` and `authenticated` have no table grants; explicit deny-all RLS policies are also present for all seven tables after the hardening migration.
- [ ] Re-run Supabase security and performance advisors after the hardening migration and confirm the seven no-policy findings and three missing foreign-key index findings are gone. Existing unrelated GenomeGuard advisor notices must be reviewed by the GenomeGuard owner, not changed by BharatSim.
- [ ] Configure the server-only database URL and verify readiness and persisted run/analysis/worker records.
- [ ] Test restart durability, duplicate callbacks, stale leases and cross-user access denial.
- [ ] Do not mark the product production-ready until the explicit blockers above are closed.
