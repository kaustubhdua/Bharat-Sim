# Supabase persistence for BharatSim

## Scope and data boundary

BharatSim uses the Supabase project **common 1** (ref hkyieaovolkethovyenb, ap-south-1) as its planned PostgreSQL persistence target. That project already contains GenomeGuard objects. The migration in this repository creates only the separate bharatsim schema and does not rename, drop, or modify any genomeguard object.

The bharatsim schema is deliberately excluded from Supabase Data API exposure in supabase/config.toml. Its tables have RLS enabled; anon and authenticated receive no schema/table grants, and the server-side service_role is the only Supabase API role granted table access. Never place a service-role key in the browser or a VITE_* variable.

## Migration

The versioned schema migration is:

- `supabase/migrations/20261027054905_bharatsim_core.sql` — matches the already-applied core migration version in `common 1`.
- `supabase/migrations/20261027060000_bharatsim_fk_indexes.sql` — additive indexes for the three BharatSim foreign-key paths reported by the performance advisor; apply only after reviewing the current migration history.

It creates the durable run, analysis, worker, event, artifact, quota, and audit tables plus indexes and integrity constraints. It is designed to be additive and isolated. It does not create or modify Storage buckets, change Auth settings, alter GenomeGuard security, or enable public client access.

Apply the reviewed migration to the intended Supabase project through the Supabase migration workflow, then verify the resulting bharatsim tables and run both Supabase security and performance advisors. Do not apply it to a different project by accident.

## Backend connection

Local development continues to use SQLite unless BHARATSIM_DATABASE_URL is set. To opt into the Supabase PostgreSQL path:

1. Apply the reviewed migrations in version order. The core schema version is already recorded by `common 1`; do not reapply it blindly. Verify migration history before applying the additive foreign-key index migration.
2. Set `BHARATSIM_ENV=production` and `BHARATSIM_DATABASE_URL` in the **server environment only** to a TLS-enabled PostgreSQL connection string for the intended project. Remote/production URLs must explicitly set `sslmode=require` or stronger (`verify-full` with the appropriate CA is preferred). Production startup fails closed if the database URL is missing; plaintext remote connections are rejected. Local development/test PostgreSQL may explicitly use `sslmode=disable` only on loopback/local hosts.
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

- [ ] Apply the migration to the intended project and verify all expected tables in the bharatsim schema.
- [ ] Confirm bharatsim is not in the project's exposed Data API schemas.
- [ ] Confirm anon and authenticated have no schema/table grants and cannot read/write the tables.
- [ ] Run Supabase security and performance advisors and investigate every relevant finding.
- [ ] Configure the server-only database URL and verify readiness and persisted run/analysis/worker records.
- [ ] Test restart durability, duplicate callbacks, stale leases and cross-user access denial.
- [ ] Do not mark the product production-ready until the explicit blockers above are closed.
