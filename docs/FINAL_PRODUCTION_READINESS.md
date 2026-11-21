# BharatSim — current production readiness decision

Status: NOT production-ready for public arbitrary APK execution.
Audit date: 22 November 2026.

> This file replaces the older Phase-2 readiness snapshot. Earlier all-gates-verified, ASVS Level 2, 100% ML accuracy, all-worker packet-loss support and fully-working-production statements were not supported by current evidence and must not be repeated.

## Current decision

BharatSim is a controlled-beta prototype with substantial implemented features and automated CI coverage. The full feature matrix and current evidence are maintained in:
- [Master Feature Inventory](MASTER_FEATURE_INVENTORY.md)
- [Final Product Audit](FINAL_PRODUCT_AUDIT.md)
- [Production Readiness](PRODUCTION_READINESS.md)
- [Production Release Gates](PRODUCTION_RELEASE_GATES.md)
- [Security Control Review](SECURITY_AUDIT.md)

## Release blockers

1. Vercel browser Supabase URL points to gpkyzastnibffyuxhtix, absent from the connected Supabase project list. The available active common 1 project is shared with GenomeGuard; owner confirmation is required before migrations.
2. The connected common 1 database has only four of nine BharatSim migrations; live runs and workers tables lack newer columns. It currently has zero BharatSim run rows and zero private APK objects.
3. Vercel sensitive BHARATSIM_DATABASE_URL and SUPABASE_URL values were not decrypted. No SUPABASE_SECRET_KEY or SUPABASE_SERVICE_ROLE_KEY appears in the complete visible Production environment inventory; private Storage is not demonstrated as enabled.
4. Production upload cap is 50 MB even though code supports 500 MB multipart uploads.
5. Production public execution, worker isolation and worker egress flags are all false. Personal laptop workers are not per-job isolation.
6. No production authenticated APK → isolated worker → persisted report → reopen/export acceptance journey has been proven.
7. ML/anomaly/BharatScore are heuristics/triage aids and lack independent field validation.
8. Manual accessibility and cross-platform installer acceptance remain.

## What is verified in code/CI

- JWT verification, owner-scoped API queries, quotas, signed upload code, worker lease/heartbeat/hash protocol and PostgreSQL adapter are implemented and tested.
- Timestamped migrations are exercised against clean PostgreSQL in CI.
- Backend, frontend, worker guard, frontend E2E, unified build and container checks passed on the earlier PR #138 base; final consolidated PR checks must pass on their own head.
- Android emulator CI validates a controlled fixture path; it is not proof of arbitrary APK traffic or production isolation.

## Required guardrails

Keep all three flags false until independent acceptance:
- BHARATSIM_PUBLIC_APK_EXECUTION_ENABLED=false
- BHARATSIM_WORKER_ISOLATION_ATTESTED=false
- BHARATSIM_WORKER_EGRESS_RESTRICTED=false

A READY Vercel deployment, green CI or connected personal laptop is not a production security boundary.