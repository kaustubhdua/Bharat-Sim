# BharatSim completion audit and Supabase migration plan

**Audit date:** 2026-10-27  
**Repository baseline inspected:** `main` at `cd152b415025611c4d782c3027b1642517044554`; candidate implementation tracked in PR #57 and the current release branch (2026-10-27)  
**Supabase target requested:** project `common 1`, ref `hkyieaovolkethovyenb`, region `ap-south-1`  
**Release decision:** **Not complete; not safe for public arbitrary-APK execution.**

This checklist distinguishes implementation from evidence. A checkbox is complete only when the exact release commit has reproducible test evidence and the deployed service has been verified. This document is an audit and implementation contract, not a claim that these gates have already passed.

## 1. Current verified state

- FastAPI API, React/Vite dashboard, SQLite persistence, APK archive checks and hashing, lease-based worker protocol, worker heartbeats, report/log analysis, Docker Compose local stack and CI workflows exist.
- The API supports SQLite for local development and has an opt-in PostgreSQL adapter (`BHARATSIM_DATABASE_URL`). A clean PostgreSQL 17 CI job applies the BharatSim core and foreign-key-index migrations from zero and tests API persistence across a process restart. This is real local PostgreSQL evidence, not proof that the deployed API is connected to `common 1`; the server-side database URL and a live application read/write test remain release gates.
- The UI intentionally labels sample logs and persona targets as illustrative/requested rather than measured device evidence. It also describes packet loss and CPU throttling as unsupported.
- The worker startup/registration diagnostics and pre-upload heartbeat assertion are implemented in the current candidate. A later emulator run exposed a second real issue: the worker launched `worker/runner.py` as a script, so its absolute `worker.*` imports failed. The runner now adds the repository root to `sys.path`, and a regression test checks the direct-script entrypoint.
- The Appium traffic experiment also timed out because a 2 MB transfer at 256 kbps needs roughly 63 seconds before network overhead. The fixture payload was reduced to a bounded 500,000-byte HTTPS transfer, socket timeouts were tightened, and the Appium wait allows the shaped transfer to finish. The latest candidate still must pass the complete Android emulator workflow; do not claim that fix is verified until its run is green.
- The Linux `tc netem` test passes on an isolated veth path. Android emulator latency/bandwidth is separately tested through the emulator's cellular transport and a real public HTTPS transfer; packet loss and CPU throttling remain unsupported, and RAM pressure remains report-only. A requested target is not proof of an applied or measured condition.
- Pull-request state changes over time; review the live open-PR list and exact candidate checks before release.
- Docker Compose is explicitly a loopback-only local evaluation stack. No verified public production deployment or physical-device test evidence was found in this audit.

## 2. Supabase discovery and safety boundary

The requested Supabase project `common 1` (ref `hkyieaovolkethovyenb`) is active in `ap-south-1` and is shared with GenomeGuard. Do not reuse, rename, drop or modify GenomeGuard objects for BharatSim. The private `bharatsim` schema has seven tables, RLS enabled, no schema usage or table SELECT grants for `anon`/`authenticated`, and `service_role` SELECT access. The core migration filename is aligned to the already-applied remote version `20261027054905_bharatsim_core`. The additive foreign-key index migration was applied as remote version `20261027061609_bharatsim_fk_indexes`; a read-only SQL check confirmed `analyses_run_id_idx`, `artifacts_owner_id_idx`, and `workers_current_run_id_idx` exist. However, the remote history also contains four earlier GenomeGuard migration versions not present in this BharatSim repository. Do not run `supabase db push` from this repo against the shared project until the shared migration-history strategy is reconciled; do not fabricate placeholder migration files.

**Critical finding:** Supabase table inspection reports RLS disabled on 13 existing `genomeguard` tables: `schema_migrations`, `cohort_metadata`, `donors`, `genotypes`, `variants`, `relationships`, `requesters`, `requests`, `decisions`, `epsilon_ledger`, `audit_log`, `donor_access`, and `alerts`. The table metadata response warns that client roles may be able to read/write those tables. The separate security-advisor call returned no lints, so the results are inconsistent; treat the explicit table-level RLS warning as unresolved and investigate it. Do not apply blanket RLS enablement to these existing tables without designing/testing their policies: enabling RLS with no suitable policies can break legitimate access. This finding belongs to the existing GenomeGuard data boundary and must be handled by its owner.

For BharatSim, use a **strictly isolated namespace** and migration history. Preferred design: a dedicated `bharatsim` schema, with no client-facing grants by default, or a fully prefixed `bharatsim_*` set in `public` if required by the chosen API approach. Never place BharatSim data in `genomeguard` tables. Add a separate, private Storage bucket namespace for APKs and run artifacts. Before any schema write, commit the migration to GitHub and review it; do not manually mutate production tables without a migration.

## 3. Target architecture using Supabase

Supabase should replace SQLite as the durable source of truth, not replace the Android execution worker.

1. **Supabase Auth:** sign-in/session validation; stable `auth.users.id` user identity; optional team/workspace membership if collaboration is required.
2. **Supabase Postgres:** durable runs, ownership, test profiles, queue/lease state, worker heartbeat, event history, analysis metadata, artifact metadata, quota accounting and audit records.
3. **Private Supabase Storage:** APK uploads, logcat, screenshots, Appium evidence and reports. Keep objects private; issue short-lived signed download URLs only after server-side ownership authorization. Store object path, byte size, SHA-256, content type, retention deadline and run ID in Postgres.
4. **Durable dispatch:** either Supabase Queues/pgmq with a dedicated consumer, or a Postgres queue/lease table with atomic claim RPC and row locking. Preserve current lease expiry, heartbeat, retry, stale callback rejection and idempotency semantics. Do not rely on in-memory tasks.
5. **Execution worker:** a separate, disposable VM-grade worker service runs emulator/ADB/Appium jobs. It polls/claims work, downloads one authorized APK, executes under strict isolation, uploads bounded evidence, and submits an authenticated idempotent result. It must not run inside a short-lived Supabase Edge Function.
6. **FastAPI:** retain as the orchestration/control API if useful, but migrate all persistence from SQLite to Postgres and validate Supabase Auth JWTs on every user route. The API must enforce ownership in queries even if RLS is also enabled. Use a least-privileged DB role; any Supabase service-role/secret key must remain server-side and never appear in Vite `VITE_*` variables.
7. **React/Vite dashboard:** use Supabase Auth for sign-in/session, call the protected API, and show real API/worker status. Do not connect the browser directly to privileged tables or storage.
8. **Deployment:** host the static frontend on Vercel if desired; use Supabase for DB/Auth/Storage; deploy FastAPI and the isolated worker to a suitable always-on compute environment. Supabase is not a substitute for an Android emulator host. Confirm free-tier pausing/limits, storage/egress limits and operating costs before promising uptime.

Official implementation references:
- Supabase production checklist: https://supabase.com/docs/guides/deployment/going-into-prod
- Supabase Row Level Security: https://supabase.com/docs/guides/database/postgres/row-level-security
- Supabase Storage access control: https://supabase.com/docs/guides/storage/security/access-control
- Supabase private buckets: https://supabase.com/docs/guides/storage/buckets/fundamentals
- Supabase Queues / pgmq: https://supabase.com/docs/guides/queues and https://supabase.com/docs/guides/queues/pgmq
- Supabase Auth token validation guidance: https://supabase.com/docs/guides/auth/server-side/creating-a-client
- Supabase backups: https://supabase.com/docs/guides/platform/backups

## 4. Remaining work — ordered release checklist

### P0-A. Fix the current failing real-worker test

- [x] Reproduce the queued-run failure from preserved Actions logs and add bounded worker/API diagnostics on timeout.
- [x] Require the real worker to register and heartbeat before the APK is uploaded.
- [x] Fix the direct-script runner import path and add a regression test for `python worker/runner.py --help`.
- [x] Exercise deliberately failing install/invalid-APK journeys and assert they reach failed terminal states.
- [x] Add a real public HTTPS network probe on the emulator's cellular transport, measure the bounded transfer, and make the wait long enough for the constrained profile.
- [ ] Rerun the complete Android emulator workflow on the latest candidate commit; preserve artifacts and inspect the report, APK hash, logs, probe measurements, and assertions before marking the end-to-end path complete.
- [ ] Review the live open pull requests and their required checks at release time; do not rely on stale PR numbers or status snapshots in this historical audit.
- [ ] Consolidate or close superseded branches/PRs only after verifying their useful changes have been merged or intentionally discarded.

### P0-B. Build a safe Supabase migration

- [x] Validate the committed `bharatsim` schema and foreign-key-index migrations from a clean PostgreSQL 17 database in CI.
- [x] Create the isolated BharatSim schema with private grants and RLS enabled; read-only SQL verified that `anon` and `authenticated` have no schema usage/table SELECT access and `service_role` has server-side access. Do not touch `genomeguard` tables.
- [x] Align the BharatSim core/index migration filenames with the remote versions and verify the three advisor-reported foreign-key indexes exist in `common 1`.
- [ ] Reconcile the shared project's earlier GenomeGuard migration history with the repository/deployment strategy before using Supabase CLI push against `common 1`.
- [ ] Define normalized tables for users/workspaces, runs, run events, test profiles, workers, leases/attempts, analyses, artifacts, quotas and audit events. Add foreign keys, uniqueness constraints, indexes, timestamps and state-transition constraints.
- [ ] Use UUIDs or equivalent unguessable IDs for externally visible resources; every user-owned row has explicit owner/workspace identity.
- [ ] Verify the opt-in PostgreSQL adapter and migrate all active production reads/writes from SQLite only after the migration has been applied and tested; provide a tested idempotent data migration and rollback path.
- [ ] Design atomic claim/lease/reclaim/retry/ack operations; make result callbacks idempotent and reject stale leases or APK hash mismatches.
- [ ] Use a durable queue (Supabase Queues/pgmq or a transactional Postgres queue); test visibility timeout, duplicate delivery, retries, poison jobs, archival and worker crash recovery.
- [ ] Configure Auth, email confirmation/session expiry as appropriate, and verify JWT signature/issuer/audience/expiry on the FastAPI boundary.
- [ ] Add deny-by-default RLS policies and SQL policy tests for every client-exposed table. Revoke unintended `anon`/authenticated grants; policies alone do not remove grants.
- [ ] Ensure user A cannot list, read, cancel, infer or download user B's runs/reports/artifacts. Test anonymous, expired, malformed and revoked sessions.
- [ ] Keep the service-role key out of frontend bundles, logs, reports, PRs and client-visible error messages. Use separate secrets for API→DB, worker→API and storage operations.
- [ ] Create private Storage buckets for APKs and artifacts; enforce size/type limits, private access, ownership checks, generated object names, bounded signed URL expiry, hash verification, retention and deletion.
- [ ] Define rollback and migration drift checks. Verify no data loss by migrating a disposable SQLite fixture and comparing counts, hashes and run state.
- [ ] Verify backups and restore a staging copy. Supabase database backups do not include Storage objects; separately test artifact backup/retention or document acceptable loss windows.

### P0-C. Secure untrusted APK execution

- [ ] Execute every uploaded APK in a disposable VM or equivalently strong isolation boundary. A normal Docker container alone is not an adequate public multi-tenant boundary for hostile APKs.
- [ ] No host secrets, privileged container, Docker socket, host filesystem mounts or cloud metadata access from the execution environment.
- [ ] Default-deny egress; allow only explicit targets required by the test profile. Block private/link-local/cloud metadata targets and validate DNS/IP redirects against SSRF/rebinding.
- [ ] Apply per-job CPU, RAM, disk, PID, wall-clock, network, upload, concurrency and daily quotas.
- [ ] Cancellation/timeouts must terminate the full process tree, emulator, ADB, Appium and any descendants, then clean up files and leases.
- [ ] Add upload and abuse rate limits, audit trails, safe error messages, incident response and artifact deletion workflows.
- [ ] Threat-model the API, worker, APK, artifact and queue boundaries; perform an independent security review before public execution.

### P0-D. Make reports defensible and measurements real

- [ ] Add worker journeys for malformed APK, install failure, launch failure, app crash, ANR/timeout, worker death, API restart, stale lease, duplicate callback, retry exhaustion and cleanup failure.
- [ ] Prove state/report/artifact persistence across API restart and worker restart, including crash during an active lease.
- [ ] Reports must distinguish procedure status from app verdict and enumerate every assertion as pass/fail/not-run with evidence and timestamps.
- [ ] Include APK SHA-256, test profile, emulator image/API, Android build, worker revision, requested/applied/read-back/traffic-verified controls, sample count, medians/spread, retries, start/end times and report schema version.
- [ ] Pair baseline and constrained measurements on the same endpoint and transport; use repeat samples, explicit timeouts and statistical assertions that tolerate environmental noise without hiding real regressions.
- [ ] Repeatedly verify latency and bandwidth on the supported emulator transport, plus reset-to-default even after test failure.
- [ ] Implement packet loss, jitter, outage/recovery, CPU/RAM/storage/battery controls only when readback and actual traffic/device behavior can be demonstrated. Otherwise mark unsupported in API capabilities, UI, docs and reports.
- [ ] Keep fixture evidence and customer evidence separate. Never call a fixture benchmark a real customer APK result.
- [ ] Test at least one physical Android device, record limitations and compare results with emulator behavior before making device-fidelity claims.

### P1. Production deployment and operations

- [ ] Deploy frontend, FastAPI and worker as distinct services with HTTPS, correct CORS, secure headers and health/readiness endpoints that fail closed when dependencies/auth configuration are missing.
- [ ] Set secrets in hosting secret stores; rotate keys and document incident rotation.
- [ ] Configure database network restrictions/SSL where compatible with the deployment, least-privilege database access, Supabase Security Advisor review and project MFA.
- [ ] Configure monitoring/alerts for API errors, worker offline/heartbeat age, queue depth/age, failed jobs, storage growth, quota denials, latency and database exhaustion.
- [ ] Configure off-site database backups and a separate policy for Storage objects; test restore and record RPO/RTO. Check the chosen Supabase plan's backup behavior and inactivity pausing.
- [ ] Load test realistic concurrent uploads, run creation, status polling, report downloads and worker contention; establish service limits.
- [ ] Verify public URL, TLS, auth flow, upload, queued run, worker execution, report retrieval and logout against the deployed commit. Confirm deployed SHA equals the audited Git SHA.
- [ ] Document operating cost, quotas, supported devices/Android versions, maintenance windows, incident response and support contact.

### P1. Product and UI/UX completion

- [ ] Review the actual built UI at mobile, tablet and desktop widths; fix overflow, clipped text, empty/error/loading states, keyboard navigation, contrast, reduced-motion behavior and screen-reader labels.
- [ ] Keep a clear distinction among requested profile, applied control, verified control and unsupported feature. Never show a profile target as observed phone state.
- [ ] Replace all mock/demo fallback data in production flows with explicit labelled examples; ensure offline API mode disables actions that require the backend.
- [ ] Provide onboarding, auth state, helpful validation, upload progress/cancellation, queue/worker wait states, run timeline, actionable failure explanation, evidence download and clear retry/cancel actions.
- [ ] Improve report readability: summary, test assertions, provenance, constraint verification, evidence links, failure explanation, limitations and export.
- [ ] Add empty/error states for Supabase downtime, expired session, worker offline, queue backlog, upload rejection, missing report and artifact expiry.
- [ ] Run Playwright E2E against the real API and staging Supabase; add accessibility checks and Lighthouse performance/accessibility budgets.
- [ ] Ensure product language is specific and credible: do not claim broad Indian-device coverage, production readiness, or controls not actually implemented.

### P1. Security, quality and maintainability

- [ ] Add API schema/contract tests and OpenAPI review; test request body limits, multipart limits, path traversal, malicious archive metadata, callback replay and authorization bypass.
- [ ] Run dependency vulnerability scanning and update pinned dependencies; resolve failing/action-required workflows rather than ignoring them.
- [ ] Add secret scanning, static analysis, container scanning, SBOM and image pinning; make required CI checks branch-protection gates.
- [ ] Add structured redacted logs and correlation IDs across API, queue, worker and report; never log tokens, APK contents or secrets.
- [ ] Document supported versus unsupported controls, threat model, data retention/deletion, privacy, acceptable use, local setup, worker provisioning, Supabase migration, deploy/rollback and troubleshooting.
- [ ] Add a reproducible clean-room setup: clone repository, configure environment, migrate a fresh Supabase/staging DB, start services, run tests and execute the sample fixture without manual undocumented steps.

## 5. Definition of done / release gate

BharatSim may be called a **completed submission-ready MVP** only when all of the following are true on one release commit:

- [ ] Fresh environment setup succeeds from documented instructions.
- [ ] All required CI checks pass, including the Android emulator end-to-end workflow.
- [ ] Supabase migration applies cleanly from zero; no SQLite dependency remains in the deployed data path.
- [ ] Auth, RLS/grants and cross-user deny tests pass; private artifact access is verified.
- [ ] Worker isolation, quotas, egress restrictions and cleanup are demonstrated with evidence.
- [ ] Clean and failing runs reach correct states; reports and artifacts persist across restarts.
- [ ] Only advertised controls are shown as supported, and every supported control has repeatable measurement/readback evidence.
- [ ] The actual deployed URL passes smoke, security and UI checks, and its SHA matches the release commit.
- [ ] At least one physical-device run is documented, or the product is explicitly scoped as emulator-only and makes no physical-device claims.
- [ ] Backup/restore, monitoring, secret rotation, data deletion and operational cost/limits are documented and tested.
- [ ] README and demo use real evidence, label fixture data, and state limitations honestly.

**Until these gates pass, label the project “MVP / controlled beta”, not “production-ready”.** Public arbitrary APK execution stays disabled until the isolation and authorization gates are satisfied.
