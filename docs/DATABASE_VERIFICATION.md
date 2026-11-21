# BharatSim — Database Verification

**Candidate:** `75d78e108ab9b2778131847a0d25f45ac7ccd2e6`  
**Date:** 2026-11-21

## CI database coverage

The CI PostgreSQL job starts a disposable PostgreSQL 17 service, creates minimal Supabase-compatible role/auth scaffolding, applies the core, FK-index and signed-upload-size migrations on a clean database, then runs restart-persistence, quota and signed-upload test modules. The parent snapshot's job passed. Candidate SHA must have its own completed passing job before merge.

## Production observation

Read-only `/health/ready` returned HTTP 503 and reports database and private Storage unavailability. No production database write/read cycle was executed; no production test data was created.

## Tenant isolation and RLS

Migrations and server-side ownership checks exist. However, live Supabase Auth + RLS tenant isolation has not been verified with two actual users for all data resources. Do not disable RLS or add broad browser grants to make tests pass.

## Remaining requirements

- Reconcile migration history before production migration; preserve all customer data.
- Test migration rollback/reapply on a disposable copy.
- Verify FK/unique/check constraints, concurrent job submission, transaction rollback and duplicate idempotency.
- Prove user A cannot read/write user B APKs, runs, logs, telemetry, findings, reports and signed objects.
- Verify signed upload/download expiry, MIME/size enforcement, object integrity and retention cleanup.
- Verify persistence across API restart and worker crash during an active job.
