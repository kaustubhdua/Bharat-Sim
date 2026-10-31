# BharatSim Supabase completion audit — latest revalidation (2026-11-01)

This addendum supersedes older status statements below where the live repository or connected Supabase state has changed. It records read-only checks against the connected project and the merged GitHub implementation. It does not imply that the application is deployed or production-ready.

## Current verified state

- Connected Supabase project `common 1` (project ref `hkyieaovolkethovyenb`) is `ACTIVE_HEALTHY` in `ap-south-1`. It contains a separate `bharatsim` schema alongside an existing `genomeguard` schema. Do not modify GenomeGuard objects as part of BharatSim work.
- The `bharatsim` schema has seven tables: `runs`, `analyses`, `workers`, `run_events`, `artifacts`, `quotas`, and `audit_events`. RLS is enabled. Read-only privilege checks show `anon` and `authenticated` have no schema USAGE and no table privileges; `service_role` has the required table privileges. The schema is therefore not directly exposed to browser roles.
- The private Storage bucket `bharatsim-private` exists, has `public=false`, a 150 MiB file limit, and APK MIME allow-list. It currently contains zero objects. This confirms bucket configuration, not that the running API is configured with its server-only service-role credential.
- Remote migration history includes `20261027054905_bharatsim_core`, `20261027061609_bharatsim_fk_indexes`, and `20261030181640_bharatsim_private_apk_storage_bucket`.
- The Supabase Security Advisor reports informational `rls_enabled_no_policy` findings for the private BharatSim tables. Because browser roles have no schema usage/table grants, do not add permissive policies merely to silence the informational lint. If the schema is ever exposed to client roles, add tested least-privilege RLS policies first.
- GitHub main now includes optional Supabase Auth JWT verification, owner-scoped run/analysis access, cross-user regression coverage, owner-scoped run deletion, and authenticated integrity-checked report export. The frontend has optional Supabase email/password sign-in. These are code and CI facts; they do not prove live Auth provider configuration or a deployed user session.
- The run deletion flow refuses to interrupt leased/running jobs, cleans up the associated APK and run-linked analyses, and retains a cancelled record if storage cleanup fails so the owner can retry. Report export is generated from bounded database JSON and includes a stable report SHA-256 plus an export ETag. It is not yet a separate durable report object.
- GitHub CI passed on main after these changes, including backend tests, PostgreSQL integration, frontend build/E2E, worker guards, and container smoke tests.

## Still unverified / release blockers

- No BharatSim production service or public URL is configured in the connected Render/Vercel accounts.
- The API has not been shown using the live `BHARATSIM_DATABASE_URL` against `common 1`; the local default remains SQLite.
- The live `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, Auth provider settings, email-confirmation/redirect configuration, and deployed frontend publishable key have not been validated as one end-to-end deployment.
- The private bucket currently has no objects; APK upload/download/delete has not been demonstrated against the live bucket from the deployed API.
- Reports, logcat, screenshots, and Appium evidence are not yet stored as durable private objects with lifecycle/retention policies.
- VM-grade disposable APK execution, default-deny egress, enforced CPU/RAM/disk/process quotas, active worker cancellation with child-process teardown, background retention, abuse controls, and complete audit logging remain unimplemented.
- The latest Android fixture bandwidth probe candidate is still under CI revalidation; do not claim measured download bandwidth or arbitrary-app traffic shaping until the current candidate produces repeated traffic-path evidence and verified reset.
- Physical low-cost device fidelity and Sarvam translation are not verified.

**Release decision:** keep BharatSim labelled MVP / controlled beta. Do not expose public arbitrary-APK execution until isolation, live tenant/Auth configuration, quotas, artifact lifecycle, and deployment evidence are complete.

---

# BharatSim completion audit and Supabase migration plan

**Audit date:** 2026-10-27  
**Repository baseline inspected:** `main` at `0cea153935fc930275f49ef266dfa9a84d00a378` (2026-10-27)  
**Supabase target requested:** project `common 1`, ref `hkyieaovolkethovyenb`, region `ap-south-1`  
**Release decision:** **Not complete; not safe for public arbitrary-APK execution.**

This checklist distinguishes implementation from evidence. A checkbox is complete only when the exact release commit has reproducible test evidence and the deployed service has been verified. This document is an audit and implementation contract, not a claim that these gates have already passed.

## Live revalidation — 2026-10-27 11:45 IST

This section supersedes stale observations below where the live state has since changed. It records the read-only checks performed against the connected Supabase project and the GitHub repository; it does not imply that the application is production-ready.

- The current main SHA at this audit point is `0cea153935fc930275f49ef266dfa9a84d00a378`, which includes the storage-condition provenance fix. Its CI, dependency audit, and emulator workflow are running again after the merge; do not infer their outcomes before completion. Earlier main CI passed on `cd152b415025611c4d782c3027b1642517044554`, but its emulator workflow failed because the fixture upload remained `queued` for 180 seconds. Do not count the end-to-end path as passed on that earlier SHA.
- Supabase project `common 1` (`hkyieaovolkethovyenb`) is `ACTIVE_HEALTHY`, PostgreSQL 17, region `ap-south-1`.
- Live migration history now contains `20261027054905_bharatsim_core` and `20261027061609_bharatsim_fk_indexes`. The three additive indexes `analyses_run_id_idx`, `artifacts_owner_id_idx`, and `workers_current_run_id_idx` exist in schema `bharatsim`. The earlier migration-version drift has been reconciled in the live database and in the current PR branch; confirm the merged release commit retains the matching filenames.
- The shared project migration history also contains earlier GenomeGuard migration versions that are not part of this repository. **Do not run `supabase db push` from this repository against `common 1`** until the complete remote migration history is reconciled or BharatSim is moved to a dedicated Supabase project. The BharatSim core/index versions are aligned, but that does not make the entire shared-project history safe to push from this repo.
- Read-only privilege checks returned: `anon` schema usage=false, `authenticated` schema usage=false, `service_role` schema usage=true; `anon` SELECT on `bharatsim.runs`=false, `authenticated` SELECT=false, `service_role` SELECT=true. This is a private-schema posture; do not grant browser roles access until ownership policies and cross-user tests exist.
- Supabase Security Advisor currently reports seven informational `rls_enabled_no_policy` findings for the private `bharatsim` tables. Since `anon` and `authenticated` have no schema usage or table SELECT grants, this is not evidence of public read access by itself. Keep the private schema unexposed; if access is later granted to client roles, add tested least-privilege RLS policies first. Do not modify existing `genomeguard` tables or their policies as part of BharatSim work.
- The single current release candidate is [PR #64](https://github.com/kaustubhdua/Bharat-Sim/pull/64); older overlapping PRs were closed as superseded. The clean PostgreSQL integration job and worker-registration fix are included. The latest detailed emulator run [40461212967](https://github.com/kaustubhdua/Bharat-Sim/actions/runs/40461212967) failed at the network probe: Android reported `transport=UNKNOWN` and `ENETUNREACH` when connecting to the public HTTPS IP, so no measured latency/bandwidth result exists. The candidate adds device-side probe logcat diagnostics; its newest run [40461402399](https://github.com/kaustubhdua/Bharat-Sim/actions/runs/40461402399) is still in progress at this audit point. Do not claim the network-control candidate is verified until that run and any required follow-up pass.
- No Vercel project matching BharatSim was found in the connected Vercel account, and no public deployment URL has been verified. Do not claim the website is deployed. The connected account only exposed a separate linked `nihdhoom` project.
- Still not verified: application server configured with the live `BHARATSIM_DATABASE_URL`; Supabase Auth JWT validation and per-user run ownership; private artifact storage; VM-grade APK sandboxing/default-deny egress; quotas/cancellation/retention; physical low-cost device test; public deployment; and end-to-end evidence on the exact release SHA.

## 1. Current verified state

- FastAPI API, React/Vite dashboard, SQLite persistence, APK archive checks and hashing, lease-based worker protocol, worker heartbeats, report/log analysis, Docker Compose local stack and CI workflows exist.
- The API still imports `sqlite3` for local mode and defaults to SQLite. A server-side opt-in PostgreSQL adapter (`BHARATSIM_DATABASE_URL`) is now implemented and covered by adapter tests, but the deployed application is not proven to use it until the server is configured with the database URL and an integration test confirms read/write behavior against the target project.
- The UI intentionally labels sample logs and persona targets as illustrative/requested rather than measured device evidence. It also describes packet loss and CPU throttling as unsupported.
- Historical main run [40457448701](https://github.com/kaustubhdua/Bharat-Sim/actions/runs/40457448701) showed the original worker-registration failure. The current candidate fixes the worker entrypoint/import path, starts it as a module, and waits for an authenticated worker registration before APK upload.
- A later emulator run completed the API → queue/lease → ADB install/launch/logcat → callback → persisted-report path and exercised a deliberate install-signature-conflict failure. This is evidence for the worker pipeline, not for network shaping or arbitrary APK safety.
- The Linux `tc netem` namespace test measures real ping traffic and verifies cleanup. That is a separate host-side test and does not prove Android traffic follows the shaped interface.
- Pull-request state changes frequently; PR #64 is the current integration candidate. Review its exact head checks and artifacts before release.
- Docker Compose is explicitly a loopback-only local evaluation stack. No verified public production deployment or physical-device test evidence was found in this audit.

## 2. Supabase discovery and safety boundary

The requested Supabase project `common 1` (ref `hkyieaovolkethovyenb`) is active and healthy in `ap-south-1`. It is **not an empty BharatSim database**: inspection found an existing `genomeguard` schema and `public.genomeguard_deployment_status` table. Do not reuse, rename, drop or modify GenomeGuard objects for BharatSim. A dedicated `bharatsim` schema and seven tables are present, with RLS enabled, no schema usage or table SELECT grants for `anon`/`authenticated`, and `service_role` SELECT access. The remote migration history records `20261027054905_bharatsim_core` and `20261027061609_bharatsim_fk_indexes`; the current integration candidate carries matching migration filenames and a clean PostgreSQL 17 job applies both from zero. This proves reproducible local migration behavior, not live application connectivity. After the index migration, the performance advisor no longer reports unindexed BharatSim foreign keys; it reports unused indexes on empty BharatSim tables and several pre-existing GenomeGuard indexes. Do not remove indexes from either schema based only on zero usage. The security advisor reports seven informational `rls_enabled_no_policy` findings for BharatSim tables. This is intentional for now: the schema is not exposed through the Data API and `anon`/`authenticated` have no schema/table grants. Do not add permissive policies until real Auth and ownership checks exist. The separate GenomeGuard RLS finding remains for its owner; do not modify those tables as part of BharatSim work.

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

- [x] Reproduce the original queued-run failure from run [40457448701](https://github.com/kaustubhdua/Bharat-Sim/actions/runs/40457448701).
- [x] Fix the worker entrypoint/import path and require authenticated worker registration before uploading the fixture APK.
- [x] Emit bounded worker/API/worker-status diagnostics on registration and timeout without printing credentials.
- [x] Verify a successful API → queue/lease → ADB → callback → persisted-report run and a deliberate install-signature-conflict failure reaching the expected terminal state.
- [x] Capture device-side network-probe logcat when the UI probe fails.
- [ ] Fix the latest observed no-route condition (`transport=UNKNOWN`, `ENETUNREACH`), then pass repeated public HTTPS latency/bandwidth measurements and reset verification on the exact release commit. Current candidate run [40461402399](https://github.com/kaustubhdua/Bharat-Sim/actions/runs/40461402399) is still running.
- [ ] Review PR #64 checks and artifacts; keep superseded overlapping PRs closed.

### P0-B. Build a safe Supabase migration

- [x] Apply the versioned core and foreign-key-index migrations from zero in PostgreSQL 17 CI and verify their filenames match the live `common 1` migration history.
- [x] Create the isolated `bharatsim` schema, enable RLS, and revoke schema/table grants from `anon` and `authenticated`; do not touch `genomeguard` tables.
- [ ] Create/configure a dedicated least-privileged database login for the API and verify live application reads/writes using a server-only TLS database URL.
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
