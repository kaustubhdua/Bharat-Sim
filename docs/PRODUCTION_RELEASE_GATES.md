# BharatSim — production release gates (current)

Audit date: 22 November 2026
Decision: controlled beta only. No-go for public arbitrary APK execution.

Use these current sources of truth:
- [Master feature inventory](MASTER_FEATURE_INVENTORY.md)
- [Final product audit](FINAL_PRODUCT_AUDIT.md)
- [Production readiness evidence](PRODUCTION_READINESS.md)
- [Security control review](SECURITY_AUDIT.md)

## P0 — required before a production APK journey

| Gate | Current evidence | Acceptance required |
|---|---|---|
| Authoritative database/project | Vercel browser VITE_SUPABASE_URL points to gpkyzastnibffyuxhtix, absent from the connected Supabase project list. Available active common 1 project is shared with GenomeGuard. | Owner confirms intended Auth/Storage/PostgreSQL project and backup/restore plan. Do not migrate shared data by assumption. |
| Server-side persistence | Sensitive BHARATSIM_DATABASE_URL and SUPABASE_URL env entries exist, but values were not decrypted. Runtime target/connectivity are unproven. | Verify /health/ready, insert/read/update across independent invocations and restart persistence on confirmed production DB. |
| Schema/migrations | Active connected DB has 4 of 9 repository BharatSim migrations. Missing custom persona, worker claiming status, run scenario, large APK parts and personal workers. Live runs and workers tables lack newer columns. | Review and apply migrations only to confirmed BharatSim DB; verify schema version and rollback. |
| Private APK Storage | Shared project has a private 150 MiB bucket but zero objects. Vercel env listing has no SUPABASE_SECRET_KEY or SUPABASE_SERVICE_ROLE_KEY; private Storage is not demonstrated as enabled. | Configure server-only secret in correct project; verify signed upload, size/hash, multipart >50MB, worker download, deletion, expiry and retention. |
| Upload cap | Vercel BHARATSIM_MAX_UPLOAD_MB=50; code supports 500MB total with 45MB parts. | Raise cap only after private Storage multipart lifecycle passes. |
| Authentication/tenant isolation | JWT verification and owner-scoped queries/RLS migrations are implemented and tested. | Two real accounts; test read/write/delete for every run, report, analysis, worker and artifact route, including signed URL replay/expiry. |
| Worker deployment/isolation | Personal laptop workers are owner-scoped convenience workers, not per-job sandboxes. Production isolation and egress flags are false. | Dedicated per-job isolated worker, patched host, default-deny egress, resource limits, lease cleanup, teardown and independent security review. |
| End-to-end journey | API/worker code and controlled fixture tests exist; no production run/object rows were observed in connected project. | Authenticated upload → worker claim → install/execute → report callback → persisted report → reopen/export on production. |

## P1 — required before stronger feature claims

- Repeat full engine network tests with measured app traffic, negative controls and per-run proxy counters. Proxy shaping only affects apps using Android's system proxy.
- Validate network outage/recovery, packet-loss stalls and connection resets across repeated runs; keep CPU throttling unsupported and RAM provisioning-dependent.
- Validate Failure DNA stability and FixProof using two real completed runs of the same scenario.
- Independently validate backend and worker ML paths using a separately labelled external holdout, confusion matrix and calibration study.
- Validate anomaly thresholds, missing-data handling and BharatScore against repeated controlled runs.
- Verify Sarvam provider credentials, translation, TTS, STT, rate limits and failure behavior in deployed environment.
- Test personal laptop installers on supported Windows/macOS/Linux versions, key revocation, update integrity and uninstall.

## P2 — quality and operations

- Manual keyboard, focus, screen-reader, contrast and reduced-motion acceptance.
- Durable artifact retention, background expiry/deletion, backup/restore and incident response.
- Production monitoring, rate limiting, abuse controls and quota alerts.
- Deploy exact merged SHA and verify /health/live, /health/ready, Auth, API and browser smoke.

## Release guardrails

- Keep BHARATSIM_PUBLIC_APK_EXECUTION_ENABLED=false.
- Keep BHARATSIM_WORKER_ISOLATION_ATTESTED=false.
- Keep BHARATSIM_WORKER_EGRESS_RESTRICTED=false.
- Never use a personal laptop, shared CI runner, API host or Vercel function as a sandbox for arbitrary public APKs.
- A green CI run or READY Vercel build is not production acceptance.