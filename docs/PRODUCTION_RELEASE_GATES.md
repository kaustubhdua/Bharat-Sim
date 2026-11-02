# Production release gates

## Live follow-up — 2026-11-02, 04:07 UTC

This supersedes older deployment-state observations below where they conflict with the live checks in this section.

- GitHub `main` is `cbfb700f95973e0dd272f569cb02a0ffe4a35bb0`. PR [#114](https://github.com/kaustubhdua/Bharat-Sim/pull/114) contains the current serverless startup, persistence gating, and dashboard fallback fixes. Its latest head at this note is `29a1e5210e67a8d7cc20656016a3bb6ed8490507`.
- Stable frontend `https://bharat-sim-81g2.vercel.app` responds HTTP 200 and serves the login page. The stable backend `https://bharat-sim-bay.vercel.app` now responds HTTP 200 on `/health/live` and `/openapi.json`; `/health/ready` correctly returns HTTP 503 because PostgreSQL and private Storage are not configured. The current production alias is attached to PR-branch commit `f86b82b78205b638fbb4c880835d27b16533eb34` (not `main`), so it is an interim startup deployment, not the final merged release.
- A backend PR preview at commit `adb12b537bf1fe97ef9c0cccfd189682c31bdb08` reached Vercel READY but still failed at runtime: its code still bootstrapped local SQLite on a Vercel preview. PR #114 now skips both import-time cleanup and SQLite bootstrap on every Vercel/AWS serverless runtime. The end-to-end regression test imports the app in a clean Vercel-like subprocess, verifies liveness, readiness, personas, capability gating, database-backed 503s, and stateless planning without creating a SQLite file.
- On the latest code-bearing run, backend tests, frontend build, frontend E2E, PostgreSQL integration, worker-guard tests, and dependency audit passed. Container smoke and Android emulator image installation/traffic-path verification were still running at this note. Vercel preview deployment attempts for both projects were rejected by the free-plan `api-deployments-free-per-day` limit (>100 deployments in 24 hours); do not repeatedly retry. A new deployment event is required after the limit resets.
- Both Vercel projects now apply SSO protection to Preview deployments only; their production `.vercel.app` aliases are public. The app-level Supabase authentication and owner checks remain enabled for private data. The temporary protection-bypass link created by authenticated deployment inspection was revoked.
- A fresh non-decrypted Backend Production environment inventory still does **not** contain `BHARATSIM_DATABASE_URL`, `SUPABASE_SECRET_KEY`, or `SUPABASE_SERVICE_ROLE_KEY`. It does contain the expected Supabase URL, auth-required flag, private bucket name, CORS origins, and disabled worker-safety flags. Do not place credentials in GitHub, frontend `VITE_*` variables, or chat.
- Supabase `common 1` remains ACTIVE_HEALTHY on PostgreSQL 17.11. The seven `bharatsim` tables have RLS enabled and no grants to `anon` or `authenticated`. The `bharatsim-private` bucket is private, permits APK/ZIP/octet-stream MIME types, and has a 157,286,400-byte (150 MiB) limit matching the backend upload limit. No BharatSim Storage objects or application runs were present in the live checks.
- No BharatSim worker service is provisioned in the connected Render workspace; the only listed Render service is GenomeGuard. The repository worker remains an execution prototype. Keep `BHARATSIM_PUBLIC_APK_EXECUTION_ENABLED=false`, `BHARATSIM_WORKER_ISOLATION_ATTESTED=false`, and `BHARATSIM_WORKER_EGRESS_RESTRICTED=false` until a dedicated KVM/Firecracker host and default-deny egress are independently verified.

**Current release decision: NO-GO for production APK testing.** Merge only after the latest GitHub checks pass. After Vercel's limit resets, deploy the merged backend first and verify live/readiness/OpenAPI, then deploy the frontend and run the production smoke suite. The two missing backend credentials and the isolated worker host remain external provisioning gates; a green CI run or READY Vercel build does not satisfy them.

---

## Re-verified status — 2026-11-02

This is a fresh infrastructure inspection, not a production acceptance sign-off.

- GitHub `main` was `4db6dda12919d6efd8c401796bebf369feb1f0fc` at this inspection. The preceding plan commit `fc4d6b476f235363c5291719b259032cbe5250e0` passed CI ([41342189313](https://github.com/kaustubhdua/Bharat-Sim/actions/runs/41342189313)) and the dependency audit ([41342189244](https://github.com/kaustubhdua/Bharat-Sim/actions/runs/41342189244)). Checks for the Firecracker version-documentation update are pending and must be verified before claiming this latest SHA is green.
- Supabase project `common 1` (`hkyieaovolkethovyenb`) is active/healthy on PostgreSQL 17.11. The seven `bharatsim` tables exist with RLS enabled. A direct read-only SQL check confirms zero Auth users, zero runs and zero artifacts; the `bharatsim-private` bucket exists and is private. The same query confirms `anon` and `authenticated` have no USAGE on the private `bharatsim` schema while `service_role` does. This matches the intended server-only access model; do not add public policies to silence the INFO advisor.
- Supabase Security Advisor reports 30 INFO-level `rls_enabled_no_policy` findings across private `bharatsim` and `genomeguard` schemas. Treat these as intentional private-schema RLS defense-in-depth only while grants remain restricted. Revisit if any browser role is granted schema/table access.
- A fresh, non-decrypted Vercel inventory for backend project `bharat-sim` (`prj_ERsWb6vkjZ6rrch2DbQDk0z0nMXA`) lists `SUPABASE_URL`, `BHARATSIM_AUTH_REQUIRED=true`, `BHARATSIM_STORAGE_BUCKET=bharatsim-private`, and the production safety flags. It does **not** list `BHARATSIM_DATABASE_URL`, `SUPABASE_SECRET_KEY`, or `SUPABASE_SERVICE_ROLE_KEY`; hidden Production variable count is zero. This finding is scoped to this exact project/team inventory and does not assert that variables do not exist in another project/scope. No secret values were decrypted.
- Production execution safety flags remain `BHARATSIM_PUBLIC_APK_EXECUTION_ENABLED=false`, `BHARATSIM_WORKER_ISOLATION_ATTESTED=false`, and `BHARATSIM_WORKER_EGRESS_RESTRICTED=false`. Keep them false until independent worker host and egress verification.
- Vercel frontend Production is READY on application/docs commit `23f14d95b8fa986fc36fd5f6306e007e6050ff0b` (`dpl_Do49P4uhN4bfiSHZ13p1JmnGioxD`). Backend Production remains READY on `2b125971f8ab6c7c0e943d57790b4ae631021dbd` (`dpl_6852SH26Kk9dwuHv6FLtJx7jyKF4`). The frontend is ahead of the backend; these are not a coordinated release. Backend project `live=false` and SSO protection is enabled for non-custom domains.
- A previous backend deployment request was rejected by Vercel's `api-deployments-free-per-day` quota. Do not repeatedly retry or bypass the quota; make one controlled deployment attempt only after checking current quota, completing production DB/Storage configuration and selecting the exact release SHA.
- Firecracker host provisioning is not done. Upstream currently lists Firecracker v1.17.0 (2026-09-10) as supported. The worker design now pins v1.17.0 as the initial candidate, with checksum/signature and advisory re-verification immediately before install. Do not use versions affected by CVE-2026-1386 (v1.13.1 and earlier, or v1.14.0); use default seccomp, matching VMM/jailer versions, trusted root-owned jail paths and an external watchdog. See [Firecracker release policy](https://github.com/firecracker-microvm/firecracker/blob/main/docs/RELEASE_POLICY.md), [production host setup](https://github.com/firecracker-microvm/firecracker/blob/main/docs/prod-host-setup.md), [seccomp](https://github.com/firecracker-microvm/firecracker/blob/main/docs/seccomp.md), and [AWS CVE bulletin](https://aws.amazon.com/security/security-bulletins/2026-003-AWS/).

**Decision:** controlled-beta MVP only. No production launch and no arbitrary public APK execution. Production DB connectivity, Auth lifecycle, private Storage round trip, isolated worker host, egress policy, durable report retention, deployed end-to-end acceptance and physical-device scope remain unverified.

---

This document is the release checklist for turning BharatSim from a credible local/CI prototype into a safe, supportable Android resilience-testing service. It deliberately separates **implemented**, **measured**, **simulated**, and **not yet supported** behavior. A checked box requires a reproducible artifact or test result from the target revision; a code path existing is not proof that the feature works end to end.

## Current release decision

**Do not expose public APK execution yet.** The repository documents real fixture-only Android emulator runs and a local API → queue/lease → ADB → callback → saved-report path. Those results validate the source-built fixture in CI, not arbitrary uploaded APKs, multi-tenant security, physical-device fidelity, or a production deployment.

## Observed infrastructure status (2026-11-01, latest verification)

- common1 (`hkyieaovolkethovyenb`) is ACTIVE_HEALTHY in ap-south-1 on PostgreSQL 17.11.0.003. The private `bharatsim` schema contains runs, workers, analyses, artifacts, quotas, run_events and audit_events; the core, FK-index and signed-upload-size migrations are present in remote migration history.
- All seven `bharatsim` tables have RLS enabled. The `bharatsim` schema has no USAGE grant for `anon` or `authenticated`; the checked server roles `service_role` and `postgres` have access. There are no client policies on the private tables or `storage.objects`. The `bharatsim-private` bucket is private, capped at 150 MiB, and restricted to APK/ZIP/octet-stream MIME types. Do not add broad client grants or policies to silence the Supabase INFO linter; these are intentionally server-only objects. The advisor reports INFO-level `rls_enabled_no_policy` findings for private schemas, not public exposure.
- Frontend Production is READY on commit `3ed44668d4d13c49648337aaba7e098f26e07045`, which contains the current application code; later main changes add documentation and frontend-only test harness/auth tests, not runtime changes. Backend Production still serves commit `2b125971f8ab6c7c0e943d57790b4ae631021dbd`, so the frontend and backend are not on the same release. The current frontend points at the stable backend alias.
- Backend Production is missing `BHARATSIM_DATABASE_URL` and `SUPABASE_SECRET_KEY` (or legacy `SUPABASE_SERVICE_ROLE_KEY`). The worker token is also absent; `SARVAM_API_KEY` is optional. Production API startup deliberately fails closed without the database and server-only Storage credential.
- Current main CI run [41332675900](https://github.com/kaustubhdua/Bharat-Sim/actions/runs/41332675900) and dependency audit [41332675878](https://github.com/kaustubhdua/Bharat-Sim/actions/runs/41332675878) passed on code/test commit `e24a7872f7a306ee67ebd5044fd17aa0601ea572`; the frontend suite now has 31 passing tests, including four Supabase Auth tests. The latest main-branch Android emulator run [41331104452](https://github.com/kaustubhdua/Bharat-Sim/actions/runs/41331104452) passed on code commit `ee0beea4495eb41fc27003ea96585f8413ddd77b`; later main commits add documentation and frontend-only test setup/auth tests; Android worker runtime code is unchanged.
- A direct Vercel deployment request was rejected with HTTP 402 `api-deployments-free-per-day` (more than 100 deployments/day; retry-after 24 hours). Git integration did deploy the frontend, but the backend remains on the older Production commit. Do not repeatedly retry or bypass the account limit.
- Both projects retain SSO protection for non-custom domains and report `live=false`. The production APK execution flags `BHARATSIM_PUBLIC_APK_EXECUTION_ENABLED`, `BHARATSIM_WORKER_ISOLATION_ATTESTED`, and `BHARATSIM_WORKER_EGRESS_RESTRICTED` are explicitly `false`; no isolated production worker host is provisioned.
- The code and CI implement signed TUS upload, but no live Vercel-to-common1 database round trip, Auth lifecycle, private APK upload, real external worker lease, or deployed upload-to-report journey has been verified. Public APK execution remains disabled.
## P0 — Safety and tenant boundaries

- [x] Implement Supabase Auth sign-up/sign-in, asymmetric JWT verification, and owner scoping for core run/analysis/report routes in code. Live Auth provider/redirect settings and deployed-token verification remain release gates; authorization coverage for every customer-data route is tracked separately below.
- [ ] Complete cross-user denial coverage for every customer-data route, including list/read/report export/delete, analyses, and any future artifact endpoints. Current regression tests cover run listing/detail, report export, deletion, analysis listing, and worker run-ID non-disclosure; live Supabase Auth and expired-session behavior still require deployment-level verification.
- [ ] Run each untrusted APK only in a disposable VM or equivalently strong isolation boundary. No host secrets, privileged container, Docker socket, host filesystem mounts, or access to cloud metadata; default-deny egress except explicitly approved test targets.
- [ ] Enforce per-job CPU, memory, disk, process, wall-clock and network quotas. Ensure timeout/cancellation actually stops ADB, emulator, Appium and child processes.
- [x] Enforce per-user daily run and active-run quotas (default 10 per UTC day and 2 active) with per-user transaction serialization; limits are configurable in `bharatsim.quotas`.
- [ ] Add per-user upload-frequency/byte quotas, abuse controls, broader administrative/security audit coverage, and documented artifact retention/deletion. Core run lifecycle events are implemented.
- [ ] Store reports, screenshots and logs in private object storage with generated object names, authorization checks, bounded retention, and integrity hashes. The current run-report download is generated from bounded database JSON and is not durable object storage. Do not rely on a local container filesystem for multi-instance production.
- [ ] Add security tests for malformed APK archives, decompression bombs, oversized multipart bodies/results, path traversal, package-name injection, malicious redirect targets, replayed callbacks, stale leases, worker crashes and cleanup failures.
- [ ] Obtain a documented threat-model/security review before enabling public execution.

**Acceptance evidence:** tests and review results attached to the exact release commit; isolation/egress policy verified from inside the worker environment; cross-tenant tests fail closed; cancellation and cleanup tests prove no active child process or artifact remains.

## P0 — Prove what a test actually did

**Recent implementation:** the run detail page now exports an owner-scoped JSON report with SHA-256 integrity metadata. This is a download/export capability, not yet private object-storage retention or a CI artifact manifest for every customer run.

- [x] Maintain a real disposable-emulator CI journey: upload APK → validate/hash → queue → lease → install/launch → collect logcat → Appium assertions → authenticated callback → persisted report. Verified by GitHub Actions run 41331104452 using a source-built fixture APK; see the hashed CI evidence artifact. This does not validate arbitrary customer APKs.
- [ ] Add negative real-worker journeys for invalid APK/manifest, install failure, launch failure, app crash, ANR/timeout, worker termination, expired lease, duplicate/stale callback and retry exhaustion.
- [ ] Test persistence across API restart for run state, worker heartbeat state, report JSON, screenshots/logs and artifact metadata. Include crash/restart during an active lease.
- [ ] Distinguish procedure status from app verdict. A smoke runner completing is not equivalent to an app journey passing. Show each authored assertion as pass/fail/not-run with evidence and timestamps.
- [ ] Record the exact APK SHA-256, emulator image/API, OS/worker revision, test profile, requested controls, observed controls, request measurements, retry counts, start/end times and report schema version.
- [ ] Keep baseline and constrained measurements paired on the same transport and endpoint. Use repeated samples and report medians/spread, sample count, failures and environmental caveats.
- [x] For every control, distinguish requested, applied/read back, traffic-path verified and unsupported. The CI proxy records profile generation/readback and per-connection upstream/byte evidence; the worker report does not claim arbitrary-app traffic verification. A console setting alone does not prove the app's request used that path.
- [x] Keep fixture/test data unmistakably labelled as fixture evidence. The README, Appium report and artifact manifest identify the source-built fixture and explicitly limit the claim to that fixture; never present fixture metrics as customer results or general device-population claims.

**Acceptance evidence:** downloadable report and CI artifacts generated from the same run, with hashes and a clear provenance chain; a clean run and a deliberately failing run both reach correct terminal states.

## P0 — Honest constraint support

- [x] Complete repeatable latency-only and bandwidth-only fixture traffic-path experiments on the CI emulator's active Wi-Fi transport using the allowlisted CONNECT proxy. Run 41331104452 verified three samples per profile, pinned upstream IP, 64,000-byte responses, 150.41–150.43 ms injected latency, 384 kbps bandwidth shaping (1,295 ms median slowdown) and reset-to-baseline readback on successful completion. This is fixture-only evidence, not proof for arbitrary uploaded APKs.
- [ ] Add a deliberately failing or cancelled proxy run after profile activation and assert reset-to-baseline cleanup; validate additional transports separately before claiming them.
- [x] Packet loss and outage/recovery are explicitly marked unsupported in the API capability contract and dashboard. No jitter control is advertised; do not imply that these conditions are simulated.
- [x] Resource support is explicit in the API and dashboard: battery saver and bounded storage pressure are supported; upload bandwidth is control-plane-verifiable only; RAM is report-only; CPU pressure is unsupported. Do not infer low-storage or low-memory behavior from a persona label alone.
- [x] Physical-device fidelity is explicitly not claimed; the README and capability contract limit current evidence to disposable Android emulators. A physical low-cost device validation is still required before making any physical-device fidelity claim.
- [ ] Add app-specific journey authoring with selectors, assertions, waits, screenshots, error-state checks and deterministic teardown. Document unsupported apps and Appium/UiAutomator2 limitations.

**Acceptance evidence:** profile-by-profile tests and reports with requested-versus-observed values; all claimed controls have automated regression tests; reset is verified in a cleanup path.

## P1 — Production operation

- [ ] Replace SQLite/local filesystem assumptions with a production database, migrations, durable job queue, and private artifact storage before horizontally scaling API/worker instances.
- [x] Add readiness checks that accurately describe required dependencies and separate API readiness from worker availability. `/health/ready` exposes API readiness and execution readiness separately; automated tests cover database unavailable, worker offline, worker online and worker not configured.
- [ ] Add structured logs, metrics, alerts, backup/restore drills, retention jobs, incident procedures, rate limiting, TLS and secret rotation.
- [ ] Configure both Vercel projects with the runtime's exact environment-variable names, cross-origin API URL/CORS, common1 Transaction-pooler database URL, server-only Supabase secret key, and verified Supabase Auth; deploy the API, frontend and isolated worker to a controlled environment; verify HTTPS, auth, persistence after restart, health/readiness, worker heartbeat, upload-to-report flow and deployed commit SHA from the public URL.
- [ ] Add browser E2E for APK selection/upload, queued → running → report states, worker offline, API errors, narrow mobile widths, keyboard/focus/accessibility and empty/error/loading states.
- [ ] Test install/build from a clean checkout and document pinned runtime versions, reproducible setup, upgrade/migration and rollback procedures.
- [x] Integrate opt-in Sarvam translation for condensed report summaries with server-side credentials, supported-language allowlisting, a 15-second timeout, sanitized provider errors, and mocked tests. A live provider call still requires a valid `SARVAM_API_KEY`; until configured and verified, the capability must remain disabled.

## Release checklist

A release may be called **production-ready** only when all P0 items are complete, a reviewed deployment exists, and the exact deployed commit has passing CI and end-to-end evidence. P1 items must be completed or explicitly accepted by a named operator with a documented mitigation. If public deployment is not intended, label the product **local/controlled-beta only** and retain the public-execution guardrails.

For each checked item, record:
1. commit SHA and date;
2. command/workflow and environment;
3. result, including failures and skipped tests;
4. artifact link and SHA-256 where applicable;
5. known scope limits and reviewer.

## Upstream references

- [Android Emulator console networking controls](https://developer.android.com/studio/run/emulator-console) — documents delay/speed controls and network-status readback; it does not by itself prove application-level traffic measurements.
- [Android Emulator command-line options](https://developer.android.com/studio/run/emulator-commandline) — documents emulator startup options for latency and bandwidth.
- [Appium UiAutomator2 driver documentation](https://appium.github.io/appium-uiautomator2-driver/) — supported Android UI automation driver and setup.
- [Android app security best practices](https://source.android.com/docs/security/best-practices/app) — automated testing and isolation guidance.
- [GitHub Actions artifact documentation](https://docs.github.com/en/actions/using-workflows/storing-workflow-data-as-artifacts) — retaining inspectable test evidence.

These upstream references inform the checklist; they do not certify BharatSim. Re-run and record the repository's own tests for every release.
