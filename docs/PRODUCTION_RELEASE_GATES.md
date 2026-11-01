# Production release gates

This document is the release checklist for turning BharatSim from a credible local/CI prototype into a safe, supportable Android resilience-testing service. It deliberately separates **implemented**, **measured**, **simulated**, and **not yet supported** behavior. A checked box requires a reproducible artifact or test result from the target revision; a code path existing is not proof that the feature works end to end.

## Current release decision

**Do not expose public APK execution yet.** The repository documents real fixture-only Android emulator runs and a local API → queue/lease → ADB → callback → saved-report path. Those results validate the source-built fixture in CI, not arbitrary uploaded APKs, multi-tenant security, physical-device fidelity, or a production deployment.

## Observed infrastructure status (2026-11-01)

- common1 has the private `bharatsim` schema, RLS enabled on its tables, no schema USAGE for `anon`/`authenticated`, and the private `bharatsim-private` bucket. The signed-upload size migration is applied. Per-user run quotas are now enforced in code; live common1 quota-row locking is not yet verified because the Vercel API database connection is not configured.
- Vercel frontend has the correct public common1 URL/publishable key and target-specific API base URLs. Backend has the common1 URL, required Supabase JWT auth, private bucket name, CORS origins, and fail-closed Production mode; Preview is explicitly Development-only.
- Production Vercel is still missing `BHARATSIM_DATABASE_URL` and `SUPABASE_SECRET_KEY` (or legacy `SUPABASE_SERVICE_ROLE_KEY`). The worker token and Sarvam key are also not configured. The API intentionally cannot be considered production-ready without the first two.
- Both Vercel production deployments are READY and their stable aliases are assigned, but they currently serve commit `2b125971f8ab6c7c0e943d57790b4ae631021dbd`; GitHub `main` is two commits ahead at `453e417be76562288afc956e545c2d5822643e07`. Vercel's latest GitHub deployment checks report `build-rate-limit`, so the current main revision and PR previews have not been deployed.
- Vercel SSO protection remains enabled. The API's production runtime is not operationally verified and its code will fail closed until `BHARATSIM_DATABASE_URL` and `SUPABASE_SECRET_KEY` (or the legacy service-role key) are configured. The frontend's production Supabase URL/publishable key and API base URL are configured.
- Production APK worker claims now fail closed unless `BHARATSIM_PUBLIC_APK_EXECUTION_ENABLED`, `BHARATSIM_WORKER_ISOLATION_ATTESTED`, and `BHARATSIM_WORKER_EGRESS_RESTRICTED` are all true. All three production Vercel flags are explicitly set to `false`; no worker token or isolated worker host is configured.
- No isolated production Android worker host has been provisioned. See `docs/WORKER_HOST_SETUP.md` and the systemd templates in `deploy/`.
- The code and CI implement the signed TUS upload path, but no live Vercel-to-common1 upload has been verified. No arbitrary APK execution or production release is claimed.
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

- [x] Maintain a real disposable-emulator CI journey: upload APK → validate/hash → queue → lease → install/launch → collect logcat → Appium assertions → authenticated callback → persisted report. Verified by GitHub Actions run 41328703086 using a source-built fixture APK; see the hashed CI evidence artifact. This does not validate arbitrary customer APKs.
- [ ] Add negative real-worker journeys for invalid APK/manifest, install failure, launch failure, app crash, ANR/timeout, worker termination, expired lease, duplicate/stale callback and retry exhaustion.
- [ ] Test persistence across API restart for run state, worker heartbeat state, report JSON, screenshots/logs and artifact metadata. Include crash/restart during an active lease.
- [ ] Distinguish procedure status from app verdict. A smoke runner completing is not equivalent to an app journey passing. Show each authored assertion as pass/fail/not-run with evidence and timestamps.
- [ ] Record the exact APK SHA-256, emulator image/API, OS/worker revision, test profile, requested controls, observed controls, request measurements, retry counts, start/end times and report schema version.
- [ ] Keep baseline and constrained measurements paired on the same transport and endpoint. Use repeated samples and report medians/spread, sample count, failures and environmental caveats.
- [x] For every control, distinguish requested, applied/read back, traffic-path verified and unsupported. The CI proxy records profile generation/readback and per-connection upstream/byte evidence; the worker report does not claim arbitrary-app traffic verification. A console setting alone does not prove the app's request used that path.
- [x] Keep fixture/test data unmistakably labelled as fixture evidence. The README, Appium report and artifact manifest identify the source-built fixture and explicitly limit the claim to that fixture; never present fixture metrics as customer results or general device-population claims.

**Acceptance evidence:** downloadable report and CI artifacts generated from the same run, with hashes and a clear provenance chain; a clean run and a deliberately failing run both reach correct terminal states.

## P0 — Honest constraint support

- [x] Complete repeatable latency-only and bandwidth-only traffic-path experiments on the CI emulator's active Wi-Fi transport using the allowlisted CONNECT proxy. Run 41328703086 verified three samples per profile, pinned upstream IP, 64,000-byte responses, 150.5 ms injected RTT, 384 kbps bandwidth shaping and reset-to-baseline readback. This is fixture-only evidence, not proof for arbitrary uploaded APKs.
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
